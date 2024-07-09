#!/usr/bin/python
# *****************************************************************************
#  This material contains trade secrets or otherwise confidential
#  information owned by Siemens Industry Software Inc. or its
#  affiliates (collectively, "Siemens"), or its licensors. Access to
#  and use of this information is strictly limited as set forth in the
#  Customer's applicable agreements with Siemens.
# 
#  Unpublished work. Copyright 2023 Siemens
# *****************************************************************************
#############################################################################
##
## This file is a part of Simcenter Amesim.
##
#############################################################################

import ctypes
import datetime
import inspect
import math
import os
import re
import struct
import subprocess
import sys
import time
import warnings
import numpy as np
import amesim_utils
from amesim_utils import AMESimError
from amesim_utils import getSystemName

# Expose data import related functions
from data_import import *

if os.name == 'nt':
    scripting_api = ctypes.CDLL("scripting_api_interface")
elif os.name == 'posix':
    scripting_api = ctypes.CDLL("libscripting_api_interface.so")

_ResultsFromAMESim = []
_VarNamesFromAMESim = []

_PRINT_OUT = sys.stdout

_DATASET_REF = "ref"
_VL_FILE_EXT = "vl"
_RESULT_FILE_EXT = "results"
_AME_FILE_EXT = "ame"
_CIR_FILE_EXT = "cir"
_BLOB_SIZE_READ = 1000000


def _printError(mess):
    print(mess, file=sys.stderr)


def _print(mess):
    print(mess, file=_PRINT_OUT)

def _decodeBytes(bytes):
    try:
        return bytes.decode("utf8")
    except UnicodeDecodeError:
        return bytes.decode("latin1")
        

def isTkInterAppPresent():
    import gc
    import tkinter
    for obj in gc.get_objects():
        if isinstance(obj, tkinter.Tk):
            return True
    else:
        return False


class _VarInfo:
    """ Storage class for variable """

    def __init__(self,
                 vardatapath='',
                 submodelname='',
                 submodelinstance=0,
                 vartitle='',
                 varunit='',
                 varnum=-1,
                 varvectorindex=-1,
                 varcircuitid=0,
                 input=False,
                 saved=False,
                 hidden=False):
        self.vardatapath = vardatapath
        self.submodelname = submodelname
        self.submodelinstance = submodelinstance
        self.vartitle = vartitle
        self.varvectorindex = varvectorindex
        self.varunit = varunit
        self.varnum = varnum
        self.varcircuitid = varcircuitid
        self.input = input
        self.saved = saved
        self.hidden = hidden

    def __eq__(self, other):
        return self.vardatapath == other.getDataPath() and self.varnum == other.getNum()

    def __hash__(self):
        return hash(str(self.varnum) + self.vardatapath)

    def copy(self):
        return _VarInfo(self.vardatapath,
                        self.submodelname,
                        self.submodelinstance,
                        self.vartitle,
                        self.varunit,
                        self.varnum,
                        self.varvectorindex,
                        self.varcircuitid,
                        self.input,
                        self.saved,
                        self.hidden)

    def clear(self):
        self.vardatapath = ''
        self.submodelname = ''
        self.submodelinstance = 0
        self.vartitle = ''
        self.varunit = ''
        self.varnum = -1
        self.varvectorindex = -1
        self.varcircuitid = ''
        self.input = False
        self.saved = False
        self.hidden = False

    def getName(self):
        if self.hidden or self.submodelname == '_DUMMY':
            return 'HIDDEN'

        if self.varvectorindex < 0:
            if self.varunit == '' or self.varunit == 'null':
                return f'{self.submodelname}_{self.submodelinstance} {self.vartitle}'
            else:
                return f'{self.submodelname}_{self.submodelinstance} {self.vartitle} [{self.varunit}]'
        else:
            if self.varunit == '' or self.varunit == 'null':
                return f'{self.submodelname}_{self.submodelinstance} [{self.varvectorindex}] {self.vartitle}'
            else:
                return f'{self.submodelname}_{self.submodelinstance} [{self.varvectorindex}] {self.vartitle} [{self.varunit}]'

    def getName_alias(self):
        if self.hidden or self.submodelname == '_DUMMY':
            return 'HIDDEN'

        alias = self.vardatapath.split('@')[1]

        if self.varvectorindex < 0:
            if self.varunit == '' or self.varunit == 'null':
                return f'{alias} {self.vartitle}'
            else:
                return f'{alias} {self.vartitle} [{self.varunit}]'
        else:
            if self.varunit == '' or self.varunit == 'null':
                return f'{alias} [{self.varvectorindex}] {self.vartitle}'
            else:
                return f'{alias} [{self.varvectorindex}] {self.vartitle} [{self.varunit}]'

    def getName_underscore(self):
        return self.getName()

    def getName_minus(self):
        return self.getFormattedName_minus(self.getName())

    def getName_instance(self):
        return self.getFormattedName_instance(self.getName())

    def getFormattedName_underscore(self, name):
        # Try with instance
        pattern = '^(\\w+) instance (\\d+) '
        match = re.search(pattern, name)

        # Try with minus
        if match is None:
            pattern = '^(\\w+)-(\\d+) '
            match = re.search(pattern, name)

        if match is not None:
            replacement = '%s_%s ' % (match.group(1), match.group(2))
            name = re.sub(re.compile(pattern), replacement, name)

        return name

    def getFormattedName_minus(self, name):
        # Try with instance
        pattern = '^(\\w+) instance (\\d+) '
        match = re.search(pattern, name)

        # Try with underscore
        if match is None:
            pattern = '^(\\w+)_(\\d+) '
            match = re.search(pattern, name)

        if match is not None:
            replacement = '%s-%s ' % (match.group(1), match.group(2))
            name = re.sub(re.compile(pattern), replacement, name)

        return name

    def getFormattedName_instance(self, name):
        # Try with underscore
        pattern = '^(\\w+)_(\\d+) '
        match = re.search(pattern, name)

        # Try with minus
        if match is None:
            pattern = '^(\\w+)-(\\d+) '
            match = re.search(pattern, name)

        if match is not None:
            replacement = '%s instance %s ' % (match.group(1), match.group(2))
            name = re.sub(re.compile(pattern), replacement, name)

        return name

    def getDataPath(self):
        return self.vardatapath

    def getSubmodelName(self):
        return self.submodelname

    def getSubmodelInstance(self):
        return self.submodelinstance

    def getTitle(self):
        return self.vartitle

    def getUnit(self):
        return self.varunit

    def getNum(self):
        return self.varnum

    def getVectorIndex(self):
        return self.varvectorindex

    def getcircuitID(self):
        return self.varcircuitid

    def isInput(self):
        return self.input

    def isSaved(self):
        return self.saved

    def isHidden(self):
        return self.hidden

    def setDataPath(self, vardatapath):
        self.vardatapath = vardatapath

    def setSubmodelName(self, submodelname):
        self.submodelname = submodelname

    def setSubmodelInstance(self, submodelinstance):
        self.submodelinstance = submodelinstance

    def setTitle(self, vartitle):
        self.vartitle = vartitle

    def setUnit(self, varunit):
        self.varunit = varunit

    def setNum(self, varnum):
        self.varnum = varnum

    def setVectorIndex(self, vectorindex):
        self.varvectorindex = vectorindex

    def setcircuitID(self, varcircuitid):
        self.varcircuitid = varcircuitid

    def setInput(self, input):
        self.input = input

    def setSaved(self, saved):
        self.saved = saved

    def setHidden(self, hidden):
        self.hidden = hidden


class ILVariablesList(object):
    """ VL file reader class """

    # EGa: should allow specifying a data set as well
    def __init__(self, vlfilepath=None):
        self.vlfilepath = ''
        self.vlfilename = ''
        self.data_set = ''
        self.vllastreaddate = None
        self.inputs2outputs = {}
        self.outputs2inputs = {}
        self.inputvariables = []
        self.outputvariables = []
        if vlfilepath is not None:
            self.setVLPath(vlfilepath)

    def reset(self):
        self.vllastreaddate = None
        self.inputvariables = []
        self.outputvariables = []
        self.inputs2outputs = {}
        self.outputs2inputs = {}
        
    def setVLPath(self, vlfilepath, data_set=''):
        sys_name_only, sys_path = ameextractsysnameandpath(vlfilepath)

        if (self.vlfilepath, self.vlfilename) != (sys_path, sys_name_only):
            self.reset()
            self.vlfilepath = sys_path
            self.vlfilename = sys_name_only
        
        if not data_set:
            data_set = 'ref'
        else:
            data_set = str(data_set)
              
        # Dataset might point to another vl file with different CRC, need to re-parse it
        # TODO: Extend the VL API to get access to the CRC (vl file checksum) in order to know
        # when parsing is neededd
        if self.data_set != data_set:
            self.reset()
            self.data_set = data_set

    def isUpToDate(self):
        if self.vllastreaddate is not None:
            last_read = self.vllastreaddate
            last_modified = ctypes.c_uint()
            scripting_api.amevl_getLastModified(ctypes.c_char_p(self.vlfilename.encode('utf8')),
                                                ctypes.c_char_p(self.vlfilepath.encode('utf8')),
                                                ctypes.c_char_p(self.data_set.encode('utf8')),
                                                ctypes.byref(last_modified))
            last_modified = last_modified.value
            return last_read > last_modified  # FIXME: use msec instead of sec to be more precise
        else:
            return False

    def update(self):
        if not self.isUpToDate():
            self.reset()
            self.readVLFile()

    def readVLFile(self):
        scripting_api.amevl_readVarList.restype = ctypes.POINTER(VLList)
        vl_list = scripting_api.amevl_readVarList(ctypes.c_char_p(self.vlfilename.encode('utf8')),
                                                  ctypes.c_char_p(self.vlfilepath.encode('utf8')),
                                                  ctypes.c_char_p(self.data_set.encode('utf8')))
        num_vl = scripting_api.amevl_getVarsCount(vl_list)

        if not vl_list:
            scripting_api.amevl_freeVarList(vl_list)
            raise AMESimError('readVLFile', 'Unable to open %s in %s' % (self.vlfilename, self.vlfilepath))

        for i in range(num_vl):
            output_var_info = self.getVarInfoAtIndex(vl_list, i)
            if not output_var_info:
                continue
            self.outputvariables.append(output_var_info)
            scripting_api.amevl_readTieVarList.restype = ctypes.POINTER(VLList)
            tie_vl_list = scripting_api.amevl_readTieVarList(vl_list, ctypes.c_int(i))
            num_tie_vl = scripting_api.amevl_getVarsCount(tie_vl_list)

            if not tie_vl_list:
                scripting_api.amevl_freeVarList(tie_vl_list)
                scripting_api.amevl_freeVarList(vl_list)
                raise AMESimError('readVLFile', 'Unable to open %s in %s' % (self.vlfilename, self.vlfilepath))

            for j in range(num_tie_vl):
                input_var_info = self.getVarInfoAtIndex(tie_vl_list, j)
                input_var_info.setInput(True)

                # Handle variable attributes (SAVE_VALUE and VARNUM) which can be incorrectly set

                # Always rely on the output save status
                input_var_info.setSaved(output_var_info.isSaved())

                # Some TIE_VAR may have their VARNUM incorrectly set...
                # First handle HIDDEN case, which does not have any varnum defined
                # so we use the first TIE_VAR varnum
                if output_var_info.isHidden() and input_var_info.getNum() != -1:
                    output_var_info.setNum(input_var_info.getNum())

                # Handle TIE_VAR with no varnum set (e.g. exposed variables) by using the
                # output varnum
                if input_var_info.getNum() < 1 and output_var_info.getNum() != -1:
                    input_var_info.setNum(output_var_info.getNum())

                self.inputvariables.append(input_var_info)

                self.inputs2outputs[input_var_info] = output_var_info
                self.outputs2inputs[output_var_info] = input_var_info

            # destroy tie variables list here
            scripting_api.amevl_freeVarList(tie_vl_list)

        # destroy variables list here
        scripting_api.amevl_freeVarList(vl_list)
        self.vllastreaddate = time.mktime(datetime.datetime.now().timetuple())

    def getVarInfoAtIndex(self, var_list, index):
        var_info = _VarInfo()
        max_str_len = scripting_api.amevl_getMaxStringLength()
        submodel_name = ctypes.create_string_buffer(max_str_len)
        submodel_instance = ctypes.c_int()
        unit = ctypes.create_string_buffer(max_str_len)
        data_path = ctypes.create_string_buffer(max_str_len)
        title = ctypes.create_string_buffer(max_str_len)
        varnum = ctypes.c_long()
        circuit_scope_id = ctypes.c_int()
        is_saved = ctypes.c_int()
        is_hidden = ctypes.c_int()

        scripting_api.amevl_getVarAtIndex(var_list,
                                          ctypes.c_int(index),
                                          submodel_name,
                                          ctypes.byref(submodel_instance),
                                          unit,
                                          data_path,
                                          title,
                                          ctypes.byref(varnum),
                                          ctypes.byref(circuit_scope_id),
                                          ctypes.byref(is_saved),
                                          ctypes.byref(is_hidden))

        var_info.setSubmodelName(submodel_name.value.decode('utf8') if len(submodel_name.value) > 0 else '')
        var_info.setSubmodelInstance(str(submodel_instance.value if int(submodel_instance.value) != -1 else 0))
        var_info.setUnit(unit.value.decode('utf8') if len(unit.value.decode('utf8')) > 0 else '')
        var_info.setNum(int(varnum.value))
        var_info.setcircuitID(int(circuit_scope_id.value) if int(circuit_scope_id.value) != -1 else 0)
        var_info.setDataPath(data_path.value.decode('utf8') if len(data_path.value) > 0 else '')
        var_info.setSaved((True if is_saved.value == 1 else False))
        var_info.setHidden((True if is_hidden.value == 1 else False))
        full_title = title.value.decode('utf8') if len(title.value) > 0 else ''
        the_title = full_title
        # This is for backward compatibility
        match = re.search(r' \((\d+)\)$', full_title)
        if match is not None:
            var_info.setVectorIndex(int(match.group(1)))
            the_title = full_title[:full_title.rfind(' (')]
        var_info.setTitle(the_title)
        var_info.setInput(False)

        return var_info

    def getAllVariables(self):
        return self.outputvariables + self.inputvariables

    def getAllInputs(self):
        return self.inputvariables

    def getAllOutputs(self):
        return self.outputvariables

    def getVariableFromDataPath(self, datapath):
        matching_variables = []
        data = datapath

        if data.startswith('*') and data.endswith('*'):
            data = data[1:-1]
            search_fun = lambda s: s.find(data) != -1
        elif data.startswith('*'):
            data = data[1:]
            search_fun = lambda s: s.endswith(data)
        elif data.endswith('*'):
            data = data[:-1]
            search_fun = lambda s: s.startswith(data)
        else:
            search_fun = lambda s: s == data

        all_variables = self.getAllVariables()
        for variable in all_variables:
            variable_datapath = variable.getDataPath()
            if search_fun(variable_datapath):
                matching_variables.append(variable)
        return matching_variables

    def getVariableFromName(self, name):
        variable_info = _VarInfo()
        matching_variables = []
        data = variable_info.getFormattedName_underscore(name)

        if data.startswith('*') and data.endswith('*'):
            data = data[1:-1]
            search_fun = lambda s: s.find(data) != -1
        elif data.startswith('*'):
            data = data[1:]
            search_fun = lambda s: s.endswith(data)
        elif data.endswith('*'):
            data = data[:-1]
            search_fun = lambda s: s.startswith(data)
        else:
            search_fun = lambda s: s == data
        all_variables = self.getAllVariables()
        for variable in all_variables:
            variable_name = variable.getName()
            if search_fun(variable_name):
                matching_variables.append(variable)
        return matching_variables

    def getAllVariableNames(self):
        all_names = []
        for variable in self.getAllVariables():
            all_names.append(variable.getName())
        return all_names

    def getAllVariableNamesWithAlias(self):
        all_names = []
        for variable in self.getAllVariables():
            all_names.append(variable.getName_alias())
        return all_names

    def getAllVariableDataPaths(self):
        all_datapaths = []
        for variable in self.getAllVariables():
            all_datapaths += variable.getDataPath()
        return all_datapaths

    def getSavedVariable(self, variable):
        outputs = self.getAllOutputs()

        if variable in outputs:
            return variable
        else:
            return self.inputs2outputs.get(variable)

    def getInputVariable(self, output_variable):
        return self.outputs2inputs.get(output_variable)

    def getOutputVariable(self, input_variable):
        return self.inputs2outputs.get(input_variable)


_variablesList = ILVariablesList()


def ameputgpar(sysname, putpartitle, putparvalue):
    """
   ameputgpar Set AMESim global parameter

   ameputgpar('SYS', 'NAME', VAL) sets the value (VAL) of the
   global parameter NAME in the system SYS. The NAME is either
   the global parameter name or its title. The function returns
   the number of parameter set.

    examples:

    ameputgpar('circuit1', 'pipediam', 12)
    ameputgpar('cicuit1', 'pipe diameter for all pipes', 12)

   See also amegetgpar, ameputp

   Copyright (c) 2015 Siemens Industry Software NV
   """

    out_found_number = 0

    if not isinstance(sysname, str):
        raise AMESimError('ameputgpar', 'the first argument must be a text string')

    ############
    # Read GPs #
    ############
    gpar, ret = amereadgp(sysname)
    if not ret:
        return out_found_number

    ###################################################
    # To save time we set the strings with new values #
    # here, outside the loop                          #
    ###################################################
    if isinstance(putparvalue, (int, float)):
        if round(putparvalue) != putparvalue:
            newparvalue = '%23.14e' % putparvalue
        else:
            newparvalue = '%d' % putparvalue
    else:
        newparvalue = putparvalue

    #################################
    # Look for matching parameters  #
    #################################
    for gp in gpar:
        if gp['pcustom']:
            continue
        if (amestrmatch(gp['ptitle'], putpartitle) == 1) or (amestrmatch(gp['pname'], putpartitle) == 1):
            out_found_number = out_found_number + 1
            gp['pvalue'] = newparvalue

    #############
    # Write GPs #
    #############
    if out_found_number > 0:
        amewritegp(sysname, gpar)

    return out_found_number


def amegetgpar(*args):
    """
   amegetgpar Get AMESim global parameter

   amegetgpar('SYS', 'NAME', RUN_ID) gets the value of the global parameter
   NAME in the system SYS. The NAME is either the name of the global
   parameter or its title. The RUN_ID parameter is optional. In case of
   batch runs, it can be used to specify the batch run number.
   The function returns the number of parameters set, submodel,
   instance, param title, value, name, and unit as in:
   [out_found_number,out_title,out_value,out_name,out_unit]=amegetgpar(sysname)
   returns as a list all the parameters that match. With no output
   arguments it displays the parameters that match

   examples:
     [num, titles, values, names, units] = amegetgpar('circuit1', 'pipediam')

     amegetgpar('circuit1')

   See also ameputgpar, ameputp

   Copyright (c) 2015 Siemens Industry Software NV
   """

    out_found_number = 0
    out_value = []
    out_parname = []
    out_partitle = []
    out_unit = []

    if len(args) == 0:
        raise AMESimError('amegetgpar', 'amegetgpar needs at least 1 argument')

    sysname = args[0]

    if not isinstance(sysname, str):
        raise AMESimError('amegetgpar', 'the first argument must be a text string')

    runid = ''

    if len(args) == 1:
        wantedpartitle = '*'
    elif len(args) == 2:
        wantedpartitle = args[1]
    elif len(args) == 3:
        wantedpartitle = args[1]
        runid = args[2]

    ############
    # Read GPs #
    ############
    filename, path = ameextractsysnameandpath(sysname)

    gpar, ret = amereadgp(os.path.join(path, filename), runid)
    if not ret:
        return out_found_number, out_partitle, out_value, out_parname, out_unit

    for gp in gpar:
        if gp['pcustom']:
            continue
        if (amestrmatch(gp['ptitle'], wantedpartitle) == 1) or (amestrmatch(gp['pname'], wantedpartitle) == 1):
            out_found_number = out_found_number + 1
            out_partitle.append(gp['ptitle'])
            out_value.append(gp['pvalue'])
            out_parname.append(gp['pname'])
            out_unit.append(gp['punit'])

    return out_found_number, out_partitle, out_value, out_parname, out_unit


def amestrmatch(text_to_search, pattern):
    """amestrmatch is a utility script for comparing two strings.
    It deals with very simple wildcard matching '*', 'hello*',
    '*hello*'

    This function is normally not used directly. It is used by
    amegetgpar, ameputgpar, amegetcuspar, ameputcuspar, amegetvars

    Copyright (C) 2019 Siemens Industry Software NV """

    success = 0
    if (text_to_search == '') or (pattern == ''):
        return success

    # If the pattern we look for is * we match anything

    if pattern == '*':
        success = 1
        return success

    # If the strings are equal we match

    if text_to_search == pattern:
        success = 1
        return success
    # Then we start with some simple wildcard matching
    # it can deal with 'hello*', '*hello*' or '*hello'

    stars = []
    for i in range(len(pattern)):
        if pattern[i] == '*':
            stars.append(i)
    if len(stars) == 1:
        if len(pattern) - 1 > len(text_to_search):
            return success
        if stars[0] == len(pattern) - 1:
            if text_to_search[:stars[0]] == pattern[:stars[0]]:
                success = 1
        elif stars[0] == 0:
            if text_to_search[len(text_to_search) - len(pattern) + 1:] == pattern[1:]:
                success = 1
    elif (len(stars) == 2) and (stars[0] == 0) and (stars[1] == len(pattern) - 1):
        if text_to_search.find(pattern[1:-1]) != -1:
            success = 1
    return success


class SimOptions(object):
    def __init__(self):
        self.startTime = 0.0
        self.finalTime = 10.0
        self.printInterval = 0.01
        self.continuationRun = False
        self.useOldFinal = False
        self.monitorTime = True
        self.statistics = False
        self.integratorType = 'standard'
        self.tolerance = 1e-7
        self.maximumTimeStep = 1e+30
        self.simulationMode = 'dynamic'
        self.printDiscont = False
        self.holdInputs = False
        self.stabilDiagnostic = False
        self.stabilLock = False
        self.solverType = 'regular'
        self.errorType = 'mixed'
        self.minimalDiscont = False
        self.disableOptimizedSolver = False
        self.autoLAOption = False
        self.autoLAMinInterval = 0.1
        self.computeActivity = False
        self.computePower = False
        self.computeEnergy = False
        self.integrationMethod = 'Euler'
        self.integrationStep = 0.001
        self.integrationOrder = 1
        # Internal
        self._version = 4


def amegetsimopt(sys_name=None):
    """
   amegetsimopt Get the simulation options.

   sim_opt = amegetsimopt(sys_name)
         reads the simulation options (.sim) file of model sys_name and
         returns them in sim_opt.

   sim_opt = amegetsimopt()
         returns the default simulation options.

   sys_name : a complete path or just the name of the system in case the
              system is placed in the current working directory.

   sim_opt : a SimOptions instance that contains the following fields:
   General options:
      -startTime         : numeric
      -finalTime         : numeric
      -printInterval     : numeric
      -continuationRun   : boolean
      -useOldFinal       : boolean (Use old final values)
      -monitorTime       : boolean
      -statistics        : boolean
      -integratorType    : 'standard' OR 'fixed'
   Standard integrator options:
      -tolerance         : numeric
      -maximumTimeStep   : numeric
      -simulationMode    : 'stabilizing' OR 'dynamic' OR 'stab_and_dyn'
      -printDiscont      : boolean (Dynamic run -Discontinuities printout)
      -holdInputs        : boolean (Dynamic run - Hold inputs constant)
      -stabilDiagnostic  : boolean (Stablizing run - Diagnostics)
      -stabilLock        : boolean (Stablizing run - Lock non-propagating states)
      -solverType        : 'regular' OR 'cautious'
      -errorType         : 'mixed' OR 'relative' OR 'absolute'
      -minimalDiscont    : boolean (Misc. - Minimal discontinuity handling)
      -disableOptimizedSolver: boolean
      -autoLAOption      : boolean (Misc. - Automatic linearization)
      -autoLAMinInterval : numeric (Misc. - Automatic linearization - Min. time interval)
      -computeActivity   : boolean (Additional computations - Activity)
      -computePower      : boolean (Additional computations - Power)
      -computeEnergy     : boolean (Additional computations - Energy)
   Fixed step integrator options
      -integrationMethod : 'Euler' OR 'Adams-Bashforth' OR 'Runge-Kutta'
      -integrationStep   : numeric
      -integrationOrder  : numeric

   See also ameputsimopt, amerunsingle, amerunbatch.

   Copyright (C) 2019 Siemens Industry Software NV
   """

    # Create a sim_opt class with default values
    sim_opt = SimOptions()
    # return the default options if no sys_name is given
    if sys_name is None:
        return sim_opt

    # Extract system name from the string sys_name
    sys_name = getSystemName(sys_name)

    # Read the .sim file
    fileName = sys_name + "_.sim"
    try:
        file = open(fileName, "r")
    except IOError as e:
        raise AMESimError('amegetsimopt', 'Cannot open file: ' + fileName) from e

    firstLine = file.readline().strip()
    if not firstLine:
        file.close()
        raise AMESimError('amegetsimopt', 'Could not read the first line from: ' + fileName)
    secondLine = file.readline().strip()
    if not secondLine:
        file.close()
        raise AMESimError('amegetsimopt', 'Could not read thesecond line from: ' + fileName)
    file.close()

    simParams = firstLine.split()
    nParams = len(simParams)
    for i in range(nParams):
        if i == 6:
            # Order is integer
            simParams[i] = int(simParams[i])
        else:
            # The rest are float
            simParams[i] = float(simParams[i])

    simOptions = secondLine.split()
    nOptions = len(simOptions)
    for i in range(nOptions):
        simOptions[i] = int(simOptions[i])

    # Internal - Find the .sim file version
    # - before AMESim v4.1: 5 values on first line, 8 values on second line (v1)
    # - before AMESim v4.2: 5 values on first line, 9 values on second line (v2)
    # - before LMS Amesim 14: 7 values on first line, 9 values on second line (v3)
    # - from LMS Amesim 14: 8 values on first line, 10 values on second line (v4)
    if nParams == 5 and nOptions == 8:
        sim_opt._version = 1
    elif nParams == 5 and nOptions == 9:
        sim_opt._version = 2
    elif nParams == 7 and nOptions == 9:
        sim_opt._version = 3
    elif nParams == 8 and nOptions == 10:
        sim_opt._version = 4
    else:
        raise AMESimError('amegetsimopt', "Invalid number of options read from: " + fileName)

    # First read the common options (v1)
    sim_opt.startTime = simParams[0]
    sim_opt.finalTime = simParams[1]
    sim_opt.printInterval = simParams[2]
    sim_opt.maximumTimeStep = simParams[3]
    sim_opt.tolerance = simParams[4]

    # Error control type
    if simOptions[0] == 0:
        sim_opt.errorType = 'mixed'
    elif simOptions[0] == 1:
        sim_opt.errorType = 'relative'
    elif simOptions[0] == 2:
        sim_opt.errorType = 'absolute'
    else:
        raise AMESimError('amegetsimopt', 'Invalid value for error type option, read from: ' + fileName)

    # Monitor time
    if simOptions[1] == 0:
        sim_opt.monitorTime = True
    elif simOptions[1] == 2:
        sim_opt.monitorTime = False
    else:
        raise AMESimError('amegetsimopt', 'Invalid value for monitor time option, read from: ' + fileName)

    # Discontinuities printout
    if simOptions[2] == 0:
        sim_opt.printDiscont = False
    elif simOptions[2] == 1:
        sim_opt.printDiscont = True
    else:
        raise AMESimError('amegetsimopt', 'Invalid value for discontinuities printout option, read from: ' + fileName)

    # Statistics
    if simOptions[3] == 0:
        sim_opt.statistics = False
    elif simOptions[3] == 1:
        sim_opt.statistics = True
    else:
        raise AMESimError('amegetsimopt', 'Invalid value for statistics option, read from: ' + fileName)

    # Continuation run
    sim_opt.continuationRun = bool(simOptions[4] & 1)

    # Use old final value
    sim_opt.useOldFinal = bool(simOptions[4] & (1 << 1))

    # Simulation mode
    simMode = (simOptions[4] >> 2) & 0b11
    if simMode == 1:
        sim_opt.simulationMode = 'stabilizing'
    elif simMode == 2:
        sim_opt.simulationMode = 'dynamic'
    elif simMode == 3:
        sim_opt.simulationMode = 'stab_and_dyn'
    else:
        raise AMESimError('amegetsimopt', 'Invalid value for simulation mode option, read from: ' + fileName)

    # Hold inputs constant
    sim_opt.holdInputs = bool(simOptions[4] & (1 << 4))

    # Intergator type
    if simOptions[4] & (1 << 5):
        sim_opt.integratorType = "fixed"
    else:
        sim_opt.integratorType = "standard"

    # Fixed integration
    if simOptions[4] & (1 << 6):
        sim_opt.integrationMethod = 'Runge-Kutta'
    else:
        # Could be either 'Euler' or 'Adams-Bashforth'; check order to determine
        if sim_opt._version >= 3 and simParams[6] == 1:
            sim_opt.integrationMethod = 'Euler'
        else:
            sim_opt.integrationMethod = 'Adams-Bashforth'

    # Disable optimized slover
    sim_opt.disableOptimizedSolver = bool(simOptions[4] & (1 << 8))

    # Solver type
    if simOptions[5] == 0:
        sim_opt.solverType = 'regular'
    elif simOptions[5] == 1:
        sim_opt.solverType = 'cautious'
    else:
        raise AMESimError('amegetsimopt', 'Invalid value for solver type option, read from: ' + fileName)

    # Stabilizing run options
    if simOptions[6] == 0:
        sim_opt.stabilDiagnostic = False
        sim_opt.stabilLock = False
    elif simOptions[6] == 1:
        sim_opt.stabilDiagnostic = False
        sim_opt.stabilLock = True
    elif simOptions[6] == 2:
        sim_opt.stabilDiagnostic = True
        sim_opt.stabilLock = False
    elif simOptions[6] == 3:
        sim_opt.stabilDiagnostic = True
        sim_opt.stabilLock = True
    else:
        raise AMESimError('amegetsimopt', 'Invalid value for stabilizing run option, read from: ' + fileName)

    # Min.  discontinuity handling
    if simOptions[7] == 0:
        sim_opt.minimalDiscont = False
    elif simOptions[7] == 1:
        sim_opt.minimalDiscont = True
    else:
        raise AMESimError('amegetsimopt',
                          'Invalid value for min. discontinuity handling option, read from: ' + fileName)

    if sim_opt._version >= 2:
        # Compute activity
        sim_opt.computeActivity = bool(simOptions[8] & 1)
        # Compute power
        sim_opt.computePower = bool(simOptions[8] & (1 << 1))
        # Compute energy
        sim_opt.computeEnergy = bool(simOptions[8] & (1 << 2))

    if sim_opt._version >= 3:
        # Step and order (fixed step integrator)
        sim_opt.integrationStep = simParams[5]
        sim_opt.integrationOrder = simParams[6]

    if sim_opt._version >= 4:
        # Automatic linearization
        sim_opt.autoLAMinInterval = simParams[7]
        if simOptions[9] == 0:
            sim_opt.autoLAOption = False
        elif simOptions[9] == 1:
            sim_opt.autoLAOption = True
        else:
            raise AMESimError('amegetsimopt',
                              'Invalid value for automatic linearization option, read from: ' + fileName)

    return sim_opt


def ameputsimopt(sys_name, sim_opt):
    """
   ameputsimopt Write the simulation options(.sim) file.

   ameputsimopt(sys_name, sim_opt)
         writes the simulation options (.sim) file of model sys_name
         from sim_opt.

   sys_name : a complete path or just the name of the system in case the
              system is placed in the current working directory.

   sim_opt : a SimOptions instance that contains the following fields:
   General options:
      -startTime         : numeric
      -finalTime         : numeric
      -printInterval     : numeric
      -continuationRun   : boolean
      -useOldFinal       : boolean (Use old final values)
      -monitorTime       : boolean
      -statistics        : boolean
      -integratorType    : 'standard' OR 'fixed'
   Standard integrator options:
      -tolerance         : numeric
      -maximumTimeStep   : numeric
      -simulationMode    : 'stabilizing' OR 'dynamic' OR 'stab_and_dyn'
      -printDiscont      : boolean (Dynamic run -Discontinuities printout)
      -holdInputs        : boolean (Dynamic run - Hold inputs constant)
      -stabilDiagnostic  : boolean (Stablizing run - Diagnostics)
      -stabilLock        : boolean (Stablizing run - Lock non-propagating states)
      -solverType        : 'regular' OR 'cautious'
      -errorType         : 'mixed' OR 'relative' OR 'absolute'
      -minimalDiscont    : boolean (Misc. - Minimal discontinuity handling)
      -disableOptimizedSolver: boolean
      -autoLAOption      : boolean (Misc. - Automatic linearization)
      -autoLAMinInterval : numeric (Misc. - Automatic linearization - Min. time interval)
      -computeActivity   : boolean (Additional computations - Activity)
      -computePower      : boolean (Additional computations - Power)
      -computeEnergy     : boolean (Additional computations - Energy)
   Fixed step integrator options
      -integrationMethod : 'Euler' OR 'Adams-Bashforth' OR 'Runge-Kutta'
      -integrationStep   : numeric
      -integrationOrder  : numeric

   See also amegetsimopt, amerunsingle, amerunbatch.

   Copyright (C) 2019 Siemens Industry Software NV
   """

    if not isinstance(sys_name, str):
        raise AMESimError('ameputsimopt', 'The first argument must be a text string.')
    if type(sim_opt) is not SimOptions:
        raise AMESimError('ameputsimopt', 'The second argument must be a SimOptions instance.')
    if len(vars(sim_opt)) != 28:
        raise AMESimError('ameputsimopt', 'Invalid number of fields in sim_opt.')

    simParams = [None] * 8
    simOptions = [None] * 10
    simParams[0] = sim_opt.startTime
    simParams[1] = sim_opt.finalTime
    simParams[2] = sim_opt.printInterval
    simParams[3] = sim_opt.maximumTimeStep
    simParams[4] = sim_opt.tolerance
    simParams[5] = sim_opt.integrationStep
    # simParams[6] needs to be set after integration method is set
    simParams[7] = sim_opt.autoLAMinInterval
    # Error control type
    if sim_opt.errorType == 'mixed':
        simOptions[0] = 0
    elif sim_opt.errorType == 'relative':
        simOptions[0] = 1
    elif sim_opt.errorType == 'absolute':
        simOptions[0] = 2
    else:
        raise AMESimError('ameputsimopt', 'Invalid "errorType" field in sim_opt.')

    # Monitor time
    if type(sim_opt.monitorTime) is bool:
        simOptions[1] = int(not sim_opt.monitorTime) * 2
    else:
        raise AMESimError('ameputsimopt', 'Invalid "monitorTime" field in sim_opt.')

    # Discontinuities printout
    if type(sim_opt.printDiscont) is bool:
        simOptions[2] = int(sim_opt.printDiscont)
    else:
        raise AMESimError('ameputsimopt', 'Invalid "printDiscont" field in sim_opt.')

    # Statistics
    if type(sim_opt.statistics) is bool:
        simOptions[3] = int(sim_opt.statistics)
    else:
        raise AMESimError('ameputsimopt', 'Invalid "statistics" field in sim_opt.')

    # Continuation run
    runParamFlag = 0
    if type(sim_opt.continuationRun) is bool:
        runParamFlag |= int(sim_opt.continuationRun)
    else:
        raise AMESimError('ameputsimopt', 'Invalid "continuationRun" field in sim_opt.')

    # Use old final value
    if type(sim_opt.useOldFinal) is bool:
        runParamFlag |= int(sim_opt.useOldFinal) << 1
    else:
        raise AMESimError('ameputsimopt', 'Invalid "useOldFinal" field in sim_opt.')

    # Simulation mode
    if sim_opt.simulationMode == 'stabilizing':
        runParamFlag |= 1 << 2
    elif sim_opt.simulationMode == 'dynamic':
        runParamFlag |= 1 << 3
    elif sim_opt.simulationMode == 'stab_and_dyn':
        runParamFlag |= 0b11 << 2
    else:
        raise AMESimError('ameputsimopt', 'Invalid "simulationMode" field in sim_opt.')

    # Hold inputs constant
    if type(sim_opt.holdInputs) is bool:
        runParamFlag |= int(sim_opt.holdInputs) << 4
    else:
        raise AMESimError('ameputsimopt', 'Invalid "holdInputs" field in sim_opt.')

    # Intergator type
    if sim_opt.integratorType == "standard":
        pass  # nothing to do
    elif sim_opt.integratorType == "fixed":
        runParamFlag |= 1 << 5
    else:
        raise AMESimError('ameputsimopt', 'Invalid "integratorType" field in sim_opt.')

    # Integration method
    # The integration order is checked also; if not valid, a default value is forced
    if sim_opt.integrationMethod == 'Euler':
        sim_opt.integrationOrder = 1  # can only be 1
    elif sim_opt.integrationMethod == 'Adams-Bashforth':
        if sim_opt.integrationOrder not in [2, 3, 4]:
            sim_opt.integrationOrder = 2
    elif sim_opt.integrationMethod == 'Runge-Kutta':
        runParamFlag |= 1 << 6
        if sim_opt.integrationOrder not in [2, 3, 4]:
            sim_opt.integrationOrder = 2
    else:
        raise AMESimError('ameputsimopt', 'Invalid "integrationMethod" field in sim_opt.')

    simParams[6] = sim_opt.integrationOrder
    # Bit 7 of runParamFlag is batch run option. This can be safely left unset,
    # as only amepreparebatchrun will set it internaly.
    # Disable optimized slover
    if type(sim_opt.disableOptimizedSolver) is bool:
        runParamFlag |= int(sim_opt.disableOptimizedSolver) << 8
    else:
        raise AMESimError('ameputsimopt', 'Invalid "disableOptimizedSolver" field in sim_opt.')

    simOptions[4] = runParamFlag
    # Solver type
    if sim_opt.solverType == 'regular':
        simOptions[5] = 0
    elif sim_opt.solverType == 'cautious':
        simOptions[5] = 1
    else:
        raise AMESimError('ameputsimopt', 'Invalid "solverType" field in sim_opt.')

    # Stabilizing run options
    if type(sim_opt.stabilDiagnostic) is not bool:
        raise AMESimError('ameputsimopt', 'Invalid "stabilDiagnostic" field in sim_opt.')
    elif type(sim_opt.stabilLock) is not bool:
        raise AMESimError('ameputsimopt', 'Invalid "stabilLock" field in sim_opt.')
    else:
        simOptions[6] = (int(sim_opt.stabilDiagnostic) << 1) | int(sim_opt.stabilLock)

    # Min. discontinuity handling
    if type(sim_opt.minimalDiscont) is bool:
        simOptions[7] = int(sim_opt.minimalDiscont)
    else:
        raise AMESimError('ameputsimopt', 'Invalid "minimalDiscont" field in sim_opt.')

    # Compute activity
    if type(sim_opt.computeActivity) is not bool:
        raise AMESimError('ameputsimopt', 'Invalid "computeActivity" field in sim_opt.')
    elif type(sim_opt.computePower) is not bool:
        raise AMESimError('ameputsimopt', 'Invalid "computePower" field in sim_opt.')
    elif type(sim_opt.computeEnergy) is not bool:
        raise AMESimError('ameputsimopt', 'Invalid "computeEnergy" field in sim_opt.')
    else:
        simOptions[8] = int(sim_opt.computeActivity) | (int(sim_opt.computePower) << 1) | (
                int(sim_opt.computeEnergy) << 2)

    # Automatic linearization
    if type(sim_opt.autoLAOption) is bool:
        simOptions[9] = int(sim_opt.autoLAOption)
    else:
        raise AMESimError('ameputsimopt', 'Invalid "autoLAOption" field in sim_opt.')

    # Check if values are valid
    if simParams[2] <= 0:
        raise AMESimError('ameputsimopt', 'Invalid value for "printInterval" in sim_opt.')
    elif simParams[3] <= 0:
        raise AMESimError('ameputsimopt', 'Invalid value for "maximumTimeStep" in sim_opt.')
    elif simParams[4] <= 0:
        raise AMESimError('ameputsimopt', 'Invalid value for "tolerance" in sim_opt.')
    elif simParams[5] <= 0:
        raise AMESimError('ameputsimopt', 'Invalid value for "integrationStep" in sim_opt')
    elif simParams[7] <= 0:
        raise AMESimError('ameputsimopt', 'Invalid value for "autoLAMinInterval" in sim_opt')

    if min(simOptions) < 0 or simOptions[0] > 2 or simOptions[1] > 2 or simOptions[2] > 1 or \
            simOptions[3] > 1 or simOptions[4] > 511 or simOptions[5] > 1 or simOptions[6] > 3 or \
            simOptions[7] > 1 or simOptions[8] > 7:
        raise AMESimError('ameputsimopt', 'Wrong option in sim_opt.')

    # Extract system name from the string sys_name
    sys_name = getSystemName(sys_name)
    
    # Write the .sim file
    fileName = sys_name + '_.sim'
    try:
        file = open(fileName, 'w')
    except IOError as e:
        raise AMESimError('ameputsimopt', 'Cannot open file: ' + fileName) from e

    # Write only the options found in the .sim file
    # - before AMESim v4.1: 5 values on first line, 8 values on second line (v1)
    # - before AMESim v4.2: 5 values on first line, 9 values on second line (v2)
    # - before LMS Amesim 14: 7 values on first line, 9 values on second line (v3)
    # - from LMS Amesim 14: 8 values on first line, 10 values on second line (v4)
    if sim_opt._version == 1:
        file.write("%g %g %g %g %g\n" % tuple(simParams[:5]))
        file.write("%d %d %d %d %d %d %d %d\n" % tuple(simOptions[:8]))
    elif sim_opt._version == 2:
        file.write("%g %g %g %g %g\n" % tuple(simParams[:5]))
        file.write("%d %d %d %d %d %d %d %d %d\n" % tuple(simOptions[:9]))
    elif sim_opt._version == 3:
        file.write("%g %g %g %g %g %g %d\n" % tuple(simParams[:7]))
        file.write("%d %d %d %d %d %d %d %d %d\n" % tuple(simOptions[:9]))
    elif sim_opt._version == 4:
        # Use 16 digits for precision from LMS Amesim 14
        # full precision for double is 17, but 16 offers some rounding
        file.write("%.16g %.16g %.16g %.16g %.16g %.16g %d %.16g\n" % tuple(simParams[:8]))
        file.write("%d %d %d %d %d %d %d %d %d %d\n" % tuple(simOptions[:10]))
    else:
        file.close()
        raise AMESimError('ameputsimopt', 'Invalid value for "version" in sim_opt.')

    file.close()


def amerun2(sysname):
    """amerun2 Starts an AMESim executable

    amerun2('SYS') starts the executable SYS_ with the run parameters
    defined by AMESim (contain in the .sim file).

    [R, S, SYSNAME, RETVAL, MESS_STR] = amerun2('SYS') loads the results file
    with ameloadt and assigns it to R and S.
    The system name is returned in SYSNAME, and RETVAL is set to
    zero for a succesful run and other values for failed runs.
    MESS_STR is filled with any errors, warning and information from
    the simulation.

    Examples:
       amerun2('circuit1')
       [Results, VarNames, SysName, RetVal, Mess] = amerun2('circuit1')

    See also amerun, ameloadt

    Copyright (C) 2019 Siemens Industry Software NV """

    _printError('Warning: "amerun2" function is deprecated. Consider using "amerunsingle" followed by "ameloadt"'
                ' or "ameloadvarst" instead.')

    ###############
    # System name #
    ###############
    # Extract system name from the string sys_name
    system_name = getSystemName(sysname)

    ###########################################
    # Check the .SIM file #
    ###########################################
    filename = system_name + '_.sim'
    try:
        fid = open(filename, 'r')
    except IOError:
        _printError('Error: Unable to start run because simulation file ' + filename + ' is missing')
        raise AMESimError('amerun', 'the simulation file (.sim) is missing')

    fid.close()

    #############
    # Start run #
    #############
    if sys.platform == 'win32':
        exefile = system_name + '_.exe'
    else:
        if system_name[0] == '/' or system_name[0] == '.':
            exefile = system_name + '_'
        else:
            exefile = './' + system_name + '_'
    if not os.path.isfile(exefile):
        _printError('Error: ' + exefile + ' does not exist. Please compile your system first')
        raise AMESimError('amerun', 'executable does not exist')

    # Put quotation mark (") in front of filename and
    # at end of filename, if filename contains any space
    if exefile.find(' ') != -1:
        exefile = '"' + exefile + '"'

    _print('Start run ...')

    pipe = os.popen(str(exefile) + ' 2>&1', 'r')
    mess = pipe.read()
    retval = pipe.close()
    if retval is None:
        retval = 0
    if mess[-1] == '\n':
        mess = mess[:-1]

    # retval = os.system(exefile)
    _print(' ... run completed')

    if retval != 0:
        _printError('An error occurred during the run')
        _printError(mess)

    ######################
    # Load .RESULTS file #
    ######################

    R_out = []
    S_out = []
    if retval == 0:
        [R_out, S_out] = ameloadt(system_name)

    sname_out = system_name
    retval_out = retval
    mess_out = mess

    return [R_out, S_out, sname_out, retval_out, mess_out]


def amerunsingle(sys_name, sim_opt=None):
    """
   amerunsingle Start a single run simulation.

   [ret_stat, msg] = amerunsingle(sys_name)
         starts a single run simulation of model sys_name.

   [ret_stat, msg] = amerunsingle(sys_name, sim_opt)
        starts a single run simulation using the simulation options from
        sim_opt.

   sys_name  : a complete path or just the sys_name of the system in case
         the system is placed in the current working directory.
   sim_opt (optional) : a SimOptions instance that contains the simulation
         options. Check documentation of amegetsimopt for complete description.
   ret_stat : returned status, true for success, false if failure.
   msg      : run details message

   See also amegetsimopt, amerunbatch.

   Copyright (C) 2019 Siemens Industry Software NV
   """
    # Extract system name from the string sys_name
    sys_name = getSystemName(sys_name)
    
    # Write simulation options
    if sim_opt is not None:
        ameputsimopt(sys_name, sim_opt)

    if os.name == 'nt':
        exe_sys_name = sys_name + '_.exe'
    else:
        if sys_name[0] == '.' or sys_name[0] == '/':
            exe_sys_name = sys_name + '_'
        else:
            exe_sys_name = './' + sys_name + '_'

    # Put quotation mark (") in front of filename and
    # at end of filename, if filename contains any space
    if exe_sys_name.find(' ') != -1:
        exe_sys_name = '"' + exe_sys_name + '"'

    _print('Starting single run simulation ...')
    try:
        bytes_msg = subprocess.check_output(exe_sys_name,
                                            stderr=subprocess.STDOUT,
                                            stdin=subprocess.PIPE,
                                            shell=True)
    except subprocess.CalledProcessError as e:
        ret_val = e.returncode
        bytes_msg = e.output
    else:
        ret_val = 0

    _print('... simulation completed')

    if ret_val == 0:
        ret_stat = True
    else:
        ret_stat = False
    
    msg = _decodeBytes(bytes_msg)
        
    return ret_stat, msg


def ameloadt(*args):
    """ameloadt loads AMESim .results format temporal files.

    [R, S] = ameloadt('NAME') extracts temporal results
    and variables name for the system NAME and sort it in
    alphabetical order.

    The data in the .results file is placed in the list R (R
    is in fact a list of lists, i.e. each element of R is a list
    corresponding to a variable. For example R = [ var1, var2, var3]
    and var1, var2 and var3 are lists containing the corresponding
    values of the variable at each time: var1 = [ var1(t0), var1(t1), ...])
    The list R is of size the number of variables in the .var
    file and each list of this list is of size the number of
    points logged. R[0] is the time list.

    The variable names from the .var file are stored in
    the string list S.

    [R, S] = ameloadt('NAME', run_id) loads the results file of the run
    specified by run_id. A batch run can be selected by specifing its number.
    0 or 'ref' specify the reference (single) run.

    [R, S] = ameloadt('NAME', run_id, include_inputs) extracts all temporal results
    and variables name, including all the input variables if the flag is
    enabled ( by default).
    Ex: [R, S] = ameloadt('NAME','ref',False) to extract only the output variables
    of the reference run.

    [R, S, sname] = ameloadt() asks the user for the name of the system
    and returns it as last argument.

    Copyright (C) 2019 Siemens Industry Software NV """
    #
    # 2010/07/07 PGr 0098698: Deal with input variables extracting variables from vl file.
    # 2011/03/08 RPE 0107567: Add a default argument (include_inputs) to avoid performance degradation introduced
    #                         with the vl file parsing
    # 2012/08/30 RPE 0131546: Improve a lot the performance when dealing with the vl file case. Set the default
    #                         argument (include_inputs) to True
    global _ResultsFromAMESim
    global _VarNamesFromAMESim

    #####################################################
    # Constants related to Unique Identifier management #
    #####################################################
    strip_unique_identifier = True
    unique_identifier_keyword = 'Data_Path'
    unique_identifier_search_regex = ' ' + unique_identifier_keyword + r'=.*@\S*'

    ###################################
    # Check number of input arguments #
    ###################################
    if len(args) > 3:
        raise AMESimError('ameloadt',
                          'ameloadt requires at most three arguments namely the system name, the run id and the '
                          '"include input variables" flag')

    #######################
    # Ask for system name #
    #######################
    if len(args) == 0:
        name = openmyfile()
    else:
        name = args[0]

    if (name == '') or (name == ()):
        raise AMESimError('ameloadt', 'ameloadt command canceled')
    name = name.strip()

    # Extract system name from the string name
    sname = getSystemName(name)

    ########################################################################
    # Explode the system file to create some temporary files (if required) #
    ########################################################################

    if not os.path.isfile(sname + '_.cir'):
        os.system('AMELoad ' + sname)
        explode = 1
    else:
        explode = 0

    ######################################
    # Read time results in .results file #
    ######################################

    if len(args) >= 2 and args[1] != 0 and args[1] != 'ref':
        filename = sname + '_.results.' + str(args[1])
    else:
        filename = sname + '_.results'

    try:
        fid = open(filename, 'rb')
    except IOError:
        raise AMESimError('ameloadt', 'unable to read ' + filename)

    (nout,) = struct.unpack('i', fid.read(4))
    (nvar,) = struct.unpack('i', fid.read(4))

    saved = list(range(1, abs(nvar) + 1))
    if nvar == 0:
        raise AMESimError('ameloadt', 'there is no saved variable in your system')
    elif nvar < 0:
        nvar = abs(nvar)  # abs for selective save
        array = np.fromfile(fid, np.dtype('i'), nvar) + 1
        saved = array.tolist()
    nvar = nvar + 1  # +1 for time

    # Use numpy.fromfile instead of unpack for performance
    try:
        array = np.fromfile(fid, np.dtype('d'), nvar * nout)
        array = array.reshape(nout, nvar)
        array = np.transpose(array)

        R = array.tolist()
    except MemoryError:
        fid.close()
        raise AMESimError("ameloadt", "Cannot allocate results array.\n"
                                      "Reduce the number of saved variables or/and number of points, or consider\n"
                                      "using the ameloadtvarst with loads results for a specify set of variables.")
    fid.close()

    if len(args) == 3:
        includeInputs = args[2]
    else:
        includeInputs = True

    if not includeInputs:
        #####################################
        # Read variables names in .var file #
        #####################################

        filename = sname + '_.var'
        try:
            fid = open(filename, 'rb')  # open in binary mode, decode later to support legacy encoding
        except IOError as e:
            raise AMESimError('ameloadt', 'unable to read ' + filename) from e

        S = ['time [s]']  # the first variable is the time
        nov = 1  # number of variables
        numinputwithdefaults = 0

        while 1:
            line = _decodeBytes(fid.readline())
            if not line:
                fid.close()
                break
            line = line.strip()
            line = line.replace(' instance ', '_')

            # Strip Unique Identifier if required
            if strip_unique_identifier and line.find(unique_identifier_keyword) != -1:
                line = re.sub(unique_identifier_search_regex, "", line)

            if line.find('_DUMMY_-1') != -1:
                numinputwithdefaults = numinputwithdefaults + 1
            nov = nov + 1

            S.append(line)
        fid.close()
        # print 'len(R)='+str(len(R))

        # Remove not saved variables
        S2 = [S[0]]
        # R2 = [R[0]]

        for i in saved:
            S2.append(S[i])
            # R2.append(R[i])
        S = S2
        # R = R2
        S2 = []
        R2 = []
        # Remove input with defaults totally from the R and S vectors

        if numinputwithdefaults > 0:
            # inputwithdef = []
            # allusefullvars = []
            for i in range(len(S)):
                if S[i].find('_DUMMY_-1') == -1:
                    # allusefullvars.append(i)
                    S2.append(S[i])
                    R2.append(R[i])
            S = S2
            R = R2
    else:
        ####################################
        # Read variables names in .vl file #
        ####################################
        if len(args) >= 2 and args[1] != 0 and args[1] != 'ref':
            data_set = args[1]
            _variablesList.setVLPath(sname, data_set)
        else:
            _variablesList.setVLPath(sname)

        # variablesList.setVLPath(vl_file_path)
        _variablesList.update()

        R2 = [R[0]]
        S = ['time [s]']

        for var in _variablesList.getAllVariables():
            if var.isSaved() and var.getName() != 'HIDDEN':
                try:
                    idx = saved.index(var.getNum()) + 1
                except ValueError:
                    warnings.warn('ameloadt: an error occurred when reading %s' % var.getDataPath())
                S.append(var.getName())
                R2.append(R[idx])

        R = R2

    ########################################
    # Sort variables in alphabetical order #
    ########################################
    tups = sorted(zip(S[1:], R[1:]), key=lambda pair: pair[0])   # only sort using names, ignore variables values
    S_sorted, R_sorted = (list(t) for t in zip(*tups))
    S = [S[0]] + S_sorted
    R = [R[0]] + R_sorted

    ############################################
    # Delete the temporary files of the system #
    ############################################

    if explode:
        os.system('AMEClean -y ' + sname)

    ###########################
    # Write some information #
    ###########################
    _print('There are ' + str(len(S)) + ' variables')
    _print('There are ' + str(len(R[0])) + ' points per variable')
    ResultsFromAMESim = R
    VarNamesFromAMESim = S
    if len(args) == 0:
        return [R, S, sname]
    else:
        return [R, S]


def ameloadvarst(*args):
    """ameloadvarst loads AMESim .results format temporal files.

    [R, S] = ameloadvarst('NAME','LISTVAR') extracts temporal results
    and variable names specified in LISTVAR for the system NAME.

    The variable names used in LISTVAR must use the format:
    <SUBMODEL>_<INSTANCE> <TITLE> [<UNIT>], ex: RL04_2 torque at port 1 [Nm]

    The data in the .results file is placed in the list R (R
    is in fact a list of lists, i.e. each element of R is a list
    corresponding to a variable. For example R = [ var1, var2, var3]
    and var1, var2 and var3 are lists containing the corresponding
    values of the variable at each time: var1 = [ var1(t0), var1(t1), ...])
    The list R is of size is the number of found specified variables plus
    time by the number of points logged. R[0] is the time list.

    The specified output variables are stored in the string list S.
    S[0] is the time variable.

    [R, S] = ameloadvarst('NAME', 'LISTVAR', run_id) uses results file of the
    run specified by run_id. A batch run can be selected by specifying its
    number. 0 or 'ref' specify the reference (single) run.


    Copyright (C) 2019 Siemens Industry Software NV """

    # 2015/04/13 RPE 7356722: Improve performance by using numpy

    ###################################
    # Check number of input arguments #
    ###################################
    if len(args) > 3 or len(args) < 2:
        raise AMESimError('ameloadvarst', 'ameloadvarst requires two or three arguments, the name of the system, '
                                          'the specified output variables list and the run id')

    circuitFilePath = args[0]
    variableList = args[1]
    dataSet = args[2] if len(args) > 2 else _DATASET_REF
    return _loadVariables(circuitFilePath, variableList, dataSet, format="varname")


def ameloadvarstui(*args):
    """ameloadvarstui loads AMESim .results format temporal files.

    [R, S] = ameloadvarstui('NAME','LISTVARUI') extracts temporal results
    and variable unique identifiers specified in LISTVARUI for the system NAME.

    The variable names used in LISTVARUI must use the variable unique
    identifier, ex: torq1@rotaryload2ports_2

    The data in the .results file is placed in the list R (R
    is in fact a list of lists, i.e. each element of R is a list
    corresponding to a variable. For example R = [ var1, var2, var3]
    and var1, var2 and var3 are lists containing the corresponding
    values of the variable at each time: var1 = [ var1(t0), var1(t1), ...])
    The list R is of size is the number of found specified variables plus
    time by the number of points logged. R[0] is the time list.

    The specified output variables are stored in the string list S.
    S[0] is the time variable.

    [R, S] = ameloadvarstui('NAME', 'LISTVARUI', run_id) uses results file
    of the run specified by run_id. A batch run can be selected by
    specifying its number. 0 or 'ref' specify the reference (single) run.

    Copyright (C) 2019 Siemens Industry Software NV """

    # 2015/04/13 RPE 7356722: Improve performance by using numpy

    ###################################
    # Check number of input arguments #
    ###################################
    if len(args) > 3 or len(args) < 2:
        raise AMESimError('ameloadvarstui', 'ameloadvarstui requires two or three arguments: the name of the system,'
                                            ' the specified output variables list and the run id')

    circuitFilePath = args[0]
    variableList = args[1]
    dataSet = args[2] if len(args) > 2 else _DATASET_REF
    return _loadVariables(circuitFilePath, variableList, dataSet, format="datapath")


def _loadVariables(circuitFilePath, variableList, dataset=_DATASET_REF, format="datapath", **options):
    """

    :param circuitFilePath:
    :param variableList:
    :param dataset:
    :param format:
    :param options:
    :return:
    """
    basename, ext = os.path.splitext(circuitFilePath)
    resultFilePath = basename + "_." + _RESULT_FILE_EXT
    if dataset != _DATASET_REF and dataset != "":
        resultFilePath += f".{dataset}"

    cirFilePath = basename + "_." + _CIR_FILE_EXT

    callerFuncName = inspect.stack()[1][3]

    if not os.path.exists(cirFilePath):
        subprocess.call(["AMELoad", circuitFilePath])
        need_retar = True
    else:
        need_retar = False

    # Read result file
    try:
        fidR = open(resultFilePath, 'rb')
    except IOError as e:
        raise AMESimError(callerFuncName, f"Cannot read result file for system '{basename}'") from e

    (nout,) = struct.unpack('i', fidR.read(4))
    (nvar,) = struct.unpack('i', fidR.read(4))

    if nvar == 0:
        raise AMESimError(callerFuncName, f"there is no saved variable in '{basename}' system")
    elif nvar < 0:
        nvar = abs(nvar)  # abs for selective save
        array = np.fromfile(fidR, np.dtype('i'), nvar) + 1
        saved = array.tolist()
    else:
        saved = range(1, abs(nvar) + 1)

    nvar += 1  # +1 for time

    _variablesList.setVLPath(basename, dataset)
    _variablesList.update()

    TIME_ID = 'ame_simulation_time' if format == "datapath" else "time [s]"
    TIME_VAR_IDX = 0
    variableIds = [TIME_ID]
    savedVarIndexes = [TIME_VAR_IDX]  # for time
    unfoundVarList = []

    if format == "datapath":
        variableDict = {v.vardatapath: v for v in _variablesList.getAllVariables()}
    else:
        variableDict = {v.getName(): v for v in _variablesList.getAllVariables()}

    for varId in variableList:
        if varId == TIME_ID:
            continue  # time is already included
        try:
            var = variableDict[varId]
        except KeyError:
            unfoundVarList.append(varId)  # log not found variable
        else:
            if not var.saved:
                continue
            varnum = var.varnum
            try:
                idx = saved.index(varnum)
            except ValueError:
                unfoundVarList.append(varId)  # log not found variable
                continue
            idx += 1  # +1 for time
            savedVarIndexes.append(idx)
            variableIds.append(varId)

    nrow = min(_BLOB_SIZE_READ // nvar, nout)
    niter = math.ceil(nout / nrow) if nrow > 0 else 0
    nb_remain = nvar * nout

    resultArray = np.array([])

    for i in range(niter):
        if nb_remain - nvar * nrow < 0:
            nrow = int(nb_remain / nvar)
        nb_remain = nb_remain - nvar * nrow
        tmp = np.fromfile(fidR, np.dtype('d'), nvar * nrow)
        tmp = tmp.reshape(nrow, nvar)
        tmp = np.transpose(tmp)[savedVarIndexes]
        if not resultArray.size:
            resultArray = tmp
        else:
            try:
                resultArray = np.concatenate((resultArray, tmp), axis=1)
            except MemoryError:
                _printError(f"{callerFuncName}: not enough memory to read results file")
                break

    fidR.close()

    if niter == 0:
        # No point in result file, need to resize the resultArray to correspond to the size of variable list
        resultArray = [list() for v in variableIds]
        
    if need_retar:
        subprocess.call(["AMEClean", "-y", circuitFilePath])

    if unfoundVarList:
        _printError('Warning: the following specified variables were not found:')
        for var in unfoundVarList:
            _printError(' ' + var)

    # resultArray = resultArray.tolist()
    return resultArray, variableIds


def amegetp(*args):
    """amegetp gets the AMESim parameters from the .data file.

    amegetp('SYS') displays all parameter names and their current
    values for the system SYS.

    [par, val] = amegetp('SYS') returns all parameter names in the list par
    and their current values in the list val.

    [par, val] = amegetp('SYS', 'SUB', 'I', 'NAME') returns parameters names
    and their current values for the system SYS, submodel SUB, instance I,
    name NAME.

    [par, val] = amegetp('SYS', 'STR*') returns parameters names and their
    current values for the system SYS, with the string STR in the name.

    Examples :

      all parameters        amegetp('circuit1')
      only one              amegetp('circuit1', 'MAS01 instance 7 total mass [kg]')
      or                    amegetp('circuit1', 'MAS01-7 total mass [kg]')
      all MAS* submodels    amegetp('circuit1', 'MAS*')
      all instance 1        amegetp('circuit1', '*', 1)
                            amegetp('circuit1', 'HL000', 1, 'diam*')
      all instances         amegetp('circuit1', 'HL000', 0, 'diam*')
                            amegetp('circuit1', 'Pressure*')
                            amegetp('circuit1', '[m/s]*')

    See also ameputp, amerun, ameloadt


    Copyright (C) 2019 Siemens Industry Software NV """
    return _amegetp(False, *args)


def _amegetp(include_linked_vars, *args):
    from math import floor
    import re

    #####################################################
    # Constants related to Unique Identifier management #
    #####################################################
    strip_unique_identifier = True
    unique_identifier_keyword = 'Data_Path'
    unique_identifier_search_regex = ' ' + unique_identifier_keyword + r'=.*@\S*'

    #######################################################################
    # Recompile Flags of all submodels can be queried by calling this     #
    # function with :                                                     #
    # [parname, value, recompile] = amegetp("sysname", "Recompile_Flags") #
    #######################################################################
    query_recompile_flags = False  # Don't query recompile flags by default

    if len(args) == 0:
        raise AMESimError('amegetp', 'amegetp needs at least 1 argument')
    sysname = args[0]

    if len(args) < 2:
        if not isinstance(sysname, str):
            raise AMESimError('amegetp', 'the first argument must be a text string')
        submodel = '*'
    else:
        submodel = args[1]

    if len(args) < 3:
        if not isinstance(submodel, str):
            raise AMESimError('amegetp', 'the second argument must be a text string')
        instance = 0
        ##################################################
        #      Query recompile flags of all submodels    #
        # only when second argument is 'Recompile_Flags' #
        ##################################################
        if submodel == 'Recompile_Flags':
            submodel = '*'  # all submodels
            query_recompile_flags = True
    else:
        instance = args[2]

    if len(args) < 4:
        if isinstance(instance, str) or (instance - floor(instance) != 0):
            raise AMESimError('amegetp', 'the 3rd argument must be an integer')
        parname = '*'
    else:
        parname = args[3]

    if len(args) == 4:
        if not isinstance(parname, str):
            raise AMESimError('amegetp', 'the 4th argument must be a text string')

    if len(args) > 5:
        raise AMESimError('amegetp', 'too many input arguments')

    #######################
    # Extract system name #
    #######################
    # Extract system name from the string sysname
    sysname = getSystemName(sysname)

    #################################
    # Read values in the .data file #
    #################################
    if len(args) == 5:
        filename = sysname + '_.data.' + str(args[4])
    else:
        filename = sysname + '_.data'
    try:
        fid = open(filename, 'rb')  # open in binary mode, decode later
    except IOError as e:
        raise AMESimError('amegetp', 'unable to read ' + filename) from e
    val0 = []
    while 1:
        read_line = _decodeBytes(fid.readline())
        if not read_line:
            fid.close()
            break
        val0.append(read_line.strip())

    ##################################
    # Read parameters in .param file #
    ##################################
    if len(args) == 5:
        filename = sysname + '_.param.' + str(args[4])
    else:
        filename = sysname + '_.param'
    try:
        fid = open(filename, 'rb')  # open in binary mode, decode later to support legacy encoding
    except IOError as e:
        raise AMESimError('amegetp', 'unable to read ' + filename) from e
    par0 = []
    rec0 = []
    while 1:
        read_line = _decodeBytes(fid.readline())
        if not read_line:
            fid.close()
            break
        read_line = read_line.strip()

        #############################
        # Remove the IS_DELTA stuff #
        #############################
        read_line = re.sub(r'Is_Delta=[0-1]+', '', read_line).strip()

        #############################
        # Remove the PARAM_ID stuff #
        #############################
        read_line = re.sub(r'Param_Id=[0-9]+', '', read_line).strip()

        ################################################
        # Get and remove the Recompile_Flag if present #
        ################################################
        rf_pos = read_line.find('Recompile_Flag')
        if rf_pos != -1:
            recomp = read_line[rf_pos + 15]
            read_line = re.sub(r' Recompile_Flag=[01]', '', read_line)
        else:
            recomp = 0

        ########################################
        # Remove Unique Identifier if required #
        ########################################
        if strip_unique_identifier and read_line.find(unique_identifier_keyword):
            read_line = re.sub(unique_identifier_search_regex, '', read_line)

        ###########################################
        # Remove Linked Variable Path if required #
        ###########################################
        if read_line.find(amesim_utils.linked_variable_path_keyword):
            read_line = re.sub(amesim_utils.linked_variable_path_regex, '', read_line)

        if read_line.find(amesim_utils.is_linked_variable_regex):
            read_line = re.sub(amesim_utils.is_linked_variable_regex, '', read_line)

        par0.append(read_line.strip())
        rec0.append(recomp)

    if len(par0) != len(val0):
        raise AMESimError('amegetp',
                          'the number of values in the .data file is different to the number of parameters in the .param file')

    if submodel.find('*') != -1:
        submodel = submodel[:submodel.find('*')].strip()
    else:
        submodel = submodel.strip()

    # Try to replace the first - with a "instance"
    if (submodel.find('instance') == -1) and (submodel.find('-') != -1):
        pos = submodel.find('-')
        blankpos = submodel.find(' ')
        if blankpos == -1:
            blankpos = len(submodel)
        if pos < blankpos:
            submodel = submodel[:pos] + ' instance ' + submodel[pos + 1:]

    if instance == 0:
        instance = ''
    else:
        instance = ' instance ' + str(instance) + ' '

    # Only do this if there is a *
    if parname.find('*') != -1:
        parname = parname[:parname.find('*')].strip()

    # select parameters and values of desired submodels
    par_out = []
    val_out = []
    recompile_flags_out = []
    for i in range(len(par0)):
        param = par0[i]
        if not include_linked_vars and amesim_utils.is_linked_variable(param):
            continue

        if param.find(submodel) != -1 and param.find(instance) != -1 and param.find(parname) != -1:
            par_out.append(param)
            val_out.append(val0[i])
            recompile_flags_out.append(rec0[i])

    if query_recompile_flags:
        return [par_out, val_out, recompile_flags_out]
    else:
        return [par_out, val_out]


def ameputp(sysname, fullname, parvalue):
    """ameputp sets the AMESim parameters in the .data file

    ameputp('SYS', 'NAME', VAL) sets the value VAL of the parameter NAME
    for the system SYS

    Examples:
      ameputp('circuit1', 'HL000 instance 1 internal pipe diameter [mm]', 10)
      ameputp('circuit1', 'HL000 instance 1 internal pipe *', 10)
      ameputp('circuit1', 'HL000-1 internal pipe *', 10)

    See also amegetp, amerun, ameloadt

    Copyright (C) 2019 Siemens Industry Software NV """

    # Extract system name from the string sysname
    sysname = getSystemName(sysname)

    ###########################################
    # Read values in the .data and .par files #
    ###########################################
    [par, val, recomp] = _amegetp(True, sysname, 'Recompile_Flags')

    # Try to replace the first - with a "instance"
    if (fullname.find('instance') == -1) and (fullname.find('-') != -1):
        pos = fullname.find('-')
        blankpos = fullname.find(' ')
        if blankpos == -1:
            blankpos = len(fullname)
        if pos < blankpos:
            fullname = fullname[:pos] + ' instance ' + fullname[pos + 1:]

    #############################
    # Looking for the parameter #
    #############################

    fullname_regex = amesim_utils.convertWildcardStringToRegexString(fullname)

    indexlistfound = []

    for i in range(len(par)):
        current_param = par[i]
        is_linked_var = amesim_utils.is_linked_variable(current_param)
        if not is_linked_var:
            if re.search(fullname_regex, current_param):
                indexlistfound.append(i)

    #################################
    # Check if there is no problem  #
    #################################
    if len(indexlistfound) > 1:
        raise AMESimError('ameputp', 'there are more than one parameter having that name')
    elif len(indexlistfound) == 0:
        _printError('Can not find any parameter with that name.\n'
                    'Check if there are any unnecessary blanks and check\n'
                    'if the case (upper or lower) is correct.\n'
                    'Other problems are submodel aliased with "-" in them\n')
        return

    ###################################################################
    # prohibit from modifying a parameter whose recompile flag is set #
    ###################################################################
    if recomp[indexlistfound[0]] == "1":
        _printError("Cannot change the value of a parameter whose Recompile flag is true.")
        return

    #####################
    # Set the new value #
    #####################

    # Since the format of the data file has changed
    # it is more difficult to say that a value is
    # real, int or string. We make a half hearted attempt
    # anyway.
    # Global parameters will cause even real parameters
    # to be string anyway
    # if isinstance(parvalue, (int, float)) and ( abs(parvalue) < 2**18 ) and ( matfix(parvalue) - parvalue == 0 )
    if isinstance(parvalue, int):
        newvalue = '%-d' % parvalue
    elif isinstance(parvalue, float):
        newvalue = '%-25.14e' % parvalue
    elif isinstance(parvalue, str):
        newvalue = '%-s' % parvalue

    # print newvalue

    newvalue = str(newvalue).strip()
    # print newvalue
    for i in indexlistfound:
        val[i] = newvalue
    # print val

    ################################
    # Write data in the .data file #
    ################################
    filename = sysname + '_.data'
    try:
        fid = open(filename, 'w', encoding="latin1")
    except IOError as e:
        raise AMESimError('ameputp', 'unable to write to ' + filename) from e

    for myvalue in val:
        fid.write(str(myvalue) + '\n')
    fid.close()
    return


def amela(*args):
    """amela Sets the linearization time for an AMESim executable.

    amela('SYS') displays the linearization time
    amela('SYS', LATIME) changes the linearization time
    amela('SYS', []) resets all the linearization times.

    example:
     amela('circuit1', [1, 2.5, 3])

    See also amerun, ameloadj

    Copyright (C) 2019 Siemens Industry Software NV """

    if len(args) > 2:
        raise AMESimError('amela', 'too many input arguments')
    if len(args) == 0:
        raise AMESimError('amela', 'amela needs at least one argument')
    sysname = args[0]
    if not isinstance(sysname, str):
        raise AMESimError('amela', 'the first argument must be a text string')
    if len(args) == 2:
        latime = args[1]
        if not isinstance(latime, list):
            if not isinstance(latime, (int, float)):
                raise AMESimError('amela', 'the second argument can only be a number or a list of number')
        else:
            # if len(latime) == 0:
            # raise AMESimError('amela', 'the list of number cannot be empty')
            # else:
            for var in latime:
                if not isinstance(var, (int, float)):
                    raise AMESimError('amela', 'the list must contains only numbers')


    # Extract system name from the string sysname
    sysname = getSystemName(sysname)

    ##########################
    # Read values in LA file #
    ##########################
    filename = sysname + '_.la'
    try:
        fid = open(filename, 'r')
    except IOError as e:
        raise AMESimError('amela', 'unable to read ' + filename) from e

    filecontent = []

    while 1:
        read_line = fid.readline()
        if not read_line:
            fid.close()
            break
        filecontent.append(read_line)
    theline = filecontent[0]
    nla = int(theline.split()[0])
    la0 = []
    if nla != 0:
        for i in range(0, nla):
            theline = filecontent[i + 1]
            la0.append(float(theline.strip()))

    ########################################
    # Printout the LA file if one argument #
    ########################################
    if len(args) == 1:
        if nla == 0:
            _printError('No linear analysis times are defined')
        else:
            _print('There are ' + str(nla) + ' linearization times defined :\n')
            for j in la0:
                _print(' at time = ' + str(j) + ' [s]')
            _print('\nThe LA Status is :\n')
            for k in filecontent[nla + 1:]:
                _print(k.strip() + '\n')
        return la0

    #################################
    # If two arguments, set LA time #
    #################################

    try:
        fid = open(filename, 'w')
    except IOError as e:
        raise AMESimError('amela', 'unable to write in ' + filename) from e

    if not isinstance(latime, list):
        fid.write('1 linear analysis times\n')
        fid.write('%e' % latime + '\n')
    else:
        fid.write(str(len(latime)) + ' linear analysis times\n')
        for j in latime:
            fid.write('%e' % j + '\n')

    if len(filecontent) == nla + 1:
        fid.write('0 fixed states\n')
        fid.write('0 control variables\n')
        fid.write('0 observer variables\n')
    else:
        for k in filecontent[nla + 1:]:
            fid.write(k)

    fid.close()
    if isinstance(args[1], list):
        return args[1]
    else:
        return [args[1]]


def amegetcuspar(*args):
    """amegetgpar Get AMESim parameter for a customized supercomponent/
    submodel

    amegetcuspar('SYS', 'SUBMODEL', INSTANCE, 'NAME', RUN_ID) gets
    the value  of the parameter NAME in submodel SUBMODEL for the
    system SYS. The NAME is either the parameter name or its title.
    The RUN_ID parameter is optional. In case of batch runs it can
    be used to specify the batch run number.
    The function returns: the number of parameters found, submodel,
    instance, parameter title, value, unit and parameter name as in:
    [out_found_number, out_submodel, out_instance, out_partitle, out_value, out_unit, out_parname]=amegetcuspar(sysname)
    NAME in the system SYS. The NAME is either the name of the global
    parameter or its title.
    All returned values are lists.
    An INSTANCE value of -1 means all instances.

    examples:
     amegetcuspar('circuit1', 'SUBSYSTEM', 1, 'pipediam')
     amegetcuspar('circuit1', 'SUBSYSTEM', 1, 'pipe diameter for all pipes')
     amegetcuspar('circuit1', 'SUBSYSTEM', -1, 'pipe diameter for all pipes')
     amegetcuspar('circuit1', '*', -1, 'pipediam')
     amegetcuspar('circuit1', '*')
     amegetcuspar('circuit1', 'pipediam_SUBSYSTEM_1')

    See also amegetgp, ameputp

    Copyright (c) 2015 Siemens Industry Software NV"""

    out_found_number = 0
    out_submodel = []
    out_instance = []
    out_partitle = []
    out_value = []
    out_parname = []
    out_unit = []

    wantedfullparname = ''
    wantedsubmodel = ''
    runid = ''

    if len(args) < 1:
        raise AMESimError('amegetcuspar', 'amegetcuspar needs at least one argument')
    sysname = args[0]
    if not isinstance(sysname, str):
        raise AMESimError('amegetcuspar', 'the first argument must be a text string')

    #########################################
    # Set up the search strings, depending  #
    # on the number of input arguments      #
    #########################################
    if len(args) == 1:
        wantedsubmodel = '*'
        wantedinstance = -1
        wantedpartitle = '*'
    elif len(args) == 2:
        wantedfullparname = args[1]
        wantedinstance = 0
        wantedpartitle = '*'
    elif len(args) == 4 or len(args) == 5:
        wantedsubmodel = args[1]
        wantedinstance = args[2]
        wantedpartitle = args[3]
        if len(args) == 5:
            runid = args[4]
    else:
        raise AMESimError('amegetcuspar', 'amegetcuspar needs 1, 2, 4 or 5 arguments')

    ############
    # Read GPs #
    ############
    gpar, ret = amereadgp(sysname, runid)
    if not ret:
        return out_found_number, out_submodel, out_instance, out_partitle, out_value, out_unit, out_parname

    ##################################
    # Look up for matching arguments #
    ##################################
    for gp in gpar:
        parname, submodelname, instance = amesplitparname(gp['pname'])
        if not gp['pcustom']:
            continue
        if parname == 'HIDDEN' or submodelname == 'HIDDEN':
            continue
        if (wantedfullparname and amestrmatch(gp['pname'], wantedfullparname)) \
                or (amestrmatch(submodelname, wantedsubmodel)
                    and (amestrmatch(gp['ptitle'], wantedpartitle)
                         or amestrmatch(parname, wantedpartitle))
                    and (wantedinstance == instance or wantedinstance <= 0)):
            out_found_number = out_found_number + 1
            out_partitle.append(str(gp['ptitle']))
            out_value.append(str(gp['pvalue']))
            out_parname.append(str(parname))
            out_submodel.append(str(submodelname))
            out_instance.append(int(instance))
            out_unit.append(gp['punit'])

    return out_found_number, out_submodel, out_instance, out_partitle, out_value, out_unit, out_parname


def ameputcuspar(sysname, wantedsubmodel, wantedinstance, wantedpartitle, putparvalue):
    """
   ameputcuspar Set AMESim parameter for a customized supercomponent/
   submodel

   ameputcuspar('SYS', 'SUBMODEL', INSTANCE, 'NAME', VAL) sets
   the value (VAL) of the parameter NAME in the submodel SUBMODEL
   for the system SYS. The NAME is either the name or its title.
   The function returns the number of parameters set.

     examples:

     ameputcuspar('circuit1', 'SUBSYSTEM', 1, 'pipediam', 12)
     ameputcuspar('cicuit1', 'SUBSYSTEM', 1, 'pipe diameter for all pipes', 12)
     ameputcuspar('cicuit1', 'SUBSYSTEM', -1, 'pipe diameter for all pipes', 12)
     ameputcuspar('circuit1', '*', 1, 'pipediam', 12)


   See also amegetgpar, ameputp

   Copyright (c) 2015 Siemens Industry Software NV
   """

    out_found_number = 0

    ###################################################
    # To save time we set the strings with new values #
    # here, outside the loop                          #
    ###################################################
    if isinstance(putparvalue, (int, float)):
        if round(putparvalue) != putparvalue:
            newparvalue = '%23.14e' % putparvalue
        else:
            newparvalue = '%d' % putparvalue
    else:
        newparvalue = putparvalue

    ############
    # Read GPs #
    ############
    gpar, ret = amereadgp(sysname)
    if not ret:
        return out_found_number

    #####################################
    # Look for parameters to be changed #
    # and replace their value           #
    #####################################
    for gp in gpar:
        if not gp['pcustom']:
            continue
        # Extract submodel name, submodel instance, parameter name and title
        [parname, submodelname, instance] = amesplitparname(gp['pname'])

        # Prevent changing hidden parameters (in both customized
        # and encrypted customized supercomponents)
        if gp['ptitle'] == 'HIDDEN' or submodelname == 'HIDDEN':
            continue

        # Apply match rules
        if amestrmatch(submodelname, wantedsubmodel) \
                and amestrmatch(gp['ptitle'], wantedpartitle) \
                or amestrmatch(parname, wantedpartitle) \
                and (wantedinstance == instance or wantedinstance <= 0):
            out_found_number = out_found_number + 1
            gp['pvalue'] = newparvalue  # replace by new value

    #############
    # Write GPs #
    #############
    if out_found_number > 0:
        amewritegp(sysname, gpar)

    return out_found_number


def amesplitparname(inputstring):
    """ amesplitparname splits a string into name, submodel and instance

    This function is part of the AMESim-Python interface. It should normally
    not be used directly. It is used in amegetcuspar and ameputcuspar.

    Copyright (C) 2019 by Siemens Industry Software NV """

    out_name = ''
    out_submodel = ''
    out_instance = -1

    if inputstring == '':
        return [out_name, out_submodel, out_instance]

    localstr = str(inputstring)
    stringlen = len(localstr)
    i = stringlen - 1
    found = 0
    start_instance = stringlen - 1

    while (i > -1) and (not found):
        if localstr[i] == '_':
            found = 1
            out_instance = localstr[i + 1:]
            start_instance = i
        i = i - 1

    start_submodel = start_instance

    if found and (i > -1):
        found = 0
        while (i > -1) and (not found):
            # Look for '__' separator
            if localstr[i] == '_' and i > 0 and localstr[i - 1] == '_':
                found = 1
                out_submodel = localstr[i + 1:start_instance]
                start_submodel = i - 1
            i = i - 1

    if start_submodel != stringlen - 1:
        out_name = localstr[:start_submodel]

    isnan = 0
    try:
        out_instance = int(out_instance)
    except ValueError:
        isnan = 1

    if isnan or (out_instance <= 0):
        out_instance = -1
        if out_submodel == '':
            out_submodel = str(out_instance)
    return [out_name, out_submodel, out_instance]


class GPList(ctypes.Structure):
    pass


class VLList(ctypes.Structure):
    pass


def amereadgp(*args):
    """
   amereadgp   Read global parameters file(s) and create an array
               of dictionary of parameters

   gpar, retstat = amereadgp(sys_name, run_id)

   sys_name     : a complete path or just the name of the system in case the
                 system is placed in the current working directory.
   run_id       : (optional) id of run. In case batch runs it can be used to
                 specify the batch run number.
   gpar        : an array of dictionary. Each element is a global parameter
                 described by a structure having the following fields
                   pcustom     : '1' for parameters of customized objects
                                 '0' otherwise
                   ptype       : 'integer', 'real' or 'text'
                   pname       : name of parameter
                   ptitle      : full title of parameter
                   pvalue      : value (as a character string)
                   pmin        : min value (as a character string,
                                 empty for 'text' type)
                   pmax        : max value (as a character string,
                                 empty for 'text' type)
                   pdef        : default value (as a character string)
                   punit       : unit for 'real' type, an empty string otherwise
                   pcirscope   : global parameter circuit scope id,
                                 empty for non custom parameters
                   pdatapath   : global parameter data path,
                                 empty for non custom parameters
                   pisenum     : gp is enum
                   penumstring : gp enum strings
   retstat     : returned status, true for success, false if failure

   Copyright (c) 2015 Siemens Industry Software NV
   """
    if len(args) < 1:
        raise AMESimError('amereadgp', 'at least one argument is required')
    if not isinstance(args[0], str):
        raise AMESimError('amereadgp', 'the first argument must be a text string')
    sys_name = args[0]

    if len(args) == 1:
        run_id = ''
    else:
        run_id = str(args[1])
        # add the "." if not present
        if len(run_id) > 0 and run_id[0] != '.':
            run_id = '.' + run_id

    sys_name_only, sys_path = ameextractsysnameandpath(sys_name)

    # Read the gp_list
    # scripting API expects a UTF8 encoding string but note that
    # currently, GP C API uses C function fopen to read the file and so only accept locale's encoding characters
    scripting_api.readGPList.restype = ctypes.POINTER(GPList)
    gp_list = scripting_api.readGPList(ctypes.c_char_p(sys_name_only.encode("utf8")),
                                       ctypes.c_char_p(sys_path.encode("utf8")),
                                       ctypes.c_char_p(run_id.encode("utf8")))

    if not gp_list:
        return [], False

    # Read max size of param fields
    nb_of_string_param = 9
    max_size = (ctypes.c_int * nb_of_string_param)()
    scripting_api.getMaxSizeOfFields.restype = None
    scripting_api.getMaxSizeOfFields(gp_list, max_size)

    # Read the number of parameters in the list
    num_gp = scripting_api.getNbOfGPs(gp_list)

    gpar = []
    gp_custom = ctypes.c_int()
    gp_type = ctypes.c_int()
    gp_name = ctypes.create_string_buffer(max_size[0])
    gp_title = ctypes.create_string_buffer(max_size[1])
    gp_value = ctypes.create_string_buffer(max_size[2])
    gp_unit = ctypes.create_string_buffer(max_size[3])
    gp_min = ctypes.create_string_buffer(max_size[4])
    gp_max = ctypes.create_string_buffer(max_size[5])
    gp_def = ctypes.create_string_buffer(max_size[6])
    gp_cir_scope = ctypes.create_string_buffer(max_size[7])
    gp_data_path = ctypes.create_string_buffer(max_size[8])

    gp_is_enum = ctypes.c_int()
    gp_enum_strings = ctypes.c_char_p()

    # Read each gp parameter and add it to gpar list
    for gp_idx in range(num_gp):
        ret_code = scripting_api.getGP(gp_list,
                                       ctypes.byref(ctypes.c_int(gp_idx)),
                                       ctypes.byref(gp_custom),
                                       ctypes.byref(gp_type),
                                       gp_name,
                                       gp_title,
                                       gp_value,
                                       gp_unit,
                                       gp_min,
                                       gp_max,
                                       gp_def,
                                       gp_cir_scope,
                                       gp_data_path,
                                       ctypes.byref(gp_is_enum),
                                       ctypes.byref(gp_enum_strings))

        # Return false if error encountered
        if ret_code != 0:
            scripting_api.freeGPList(gp_list)
            return [], False

        # Create each parameter
        gp = {'pcustom': gp_custom.value}
        if gp_type.value == 1:
            gp['ptype'] = 'real'
        elif gp_type.value == 2:
            gp['ptype'] = 'integer'
        elif gp_type.value == 3:
            gp['ptype'] = 'text'

        gp['pname'] = gp_name.value
        gp['pname'] = gp['pname'].decode('utf-8').strip()

        gp['ptitle'] = gp_title.value
        gp['ptitle'] = gp['ptitle'].decode('utf-8').strip()

        gp['pvalue'] = gp_value.value
        gp['pvalue'] = gp['pvalue'].decode('utf-8').strip()

        gp['punit'] = gp_unit.value
        gp['punit'] = gp['punit'].decode('utf-8').strip()

        gp['pmin'] = gp_min.value
        gp['pmin'] = gp['pmin'].decode('utf-8').strip()

        gp['pmax'] = gp_max.value
        gp['pmax'] = gp['pmax'].decode('utf-8').strip()

        gp['pdef'] = gp_def.value
        gp['pdef'] = gp['pdef'].decode('utf-8').strip()

        gp['pcirscope'] = gp_cir_scope.value
        gp['pcirscope'] = gp['pcirscope'].decode('utf-8').strip()

        gp['pdatapath'] = gp_data_path.value
        gp['pdatapath'] = gp['pdatapath'].decode('utf-8').strip()

        gp['pis_enum'] = gp_is_enum.value

        temp_string = gp_enum_strings.value
        temp_enum_list = temp_string.decode('utf-8').split('\n') if temp_string else []
        gp['penum_strings'] = [enum_item.strip() for enum_item in temp_enum_list]

        gpar.append(gp)

        scripting_api.releaseGPEnumStringsBuffer(ctypes.byref(gp_enum_strings))

    # free the gp list
    scripting_api.freeGPList(gp_list)

    return gpar, True


def amewritegp(sys_name, gpar):
    """
   amewritegp   Write an array of dictionary of parameters into a file

   retstat = amewritegp(sys_name, gpar)

   sys_name    : a complete path or just the name of the system in case the
                 system is placed in the current working directory.
   gpar        : an array of dictionary. Each element is a global parameter
                 described by a structure having the following fields
                   pcustom     : '1' for parameters of customized objects
                                 '0' otherwise
                   ptype       : 'integer', 'real' or 'text'
                   pname       : name of parameter
                   ptitle      : full title of parameter
                   pvalue      : value (as a character string)
                   pmin        : min value (as a character string,
                                 empty for 'text' type)
                   pmax        : max value (as a character string,
                                 empty for 'text' type)
                   pdef        : default value (as a character string)
                   punit       : unit for 'real' type, an empty string otherwise
                   pcirscope   : global parameter circuit scope id,
                                 empty for non custom parameters
                   pdatapath   : global parameter data path,
                                 empty for non custom parameters
                   pisenum     : gp is enum
                   penumstring : gp enum strings
   retstat     : returned status, true for success, false if failure

   Copyright (c) 2015 Siemens Industry Software NV
   """

    sys_name_only, sys_path = ameextractsysnameandpath(sys_name)

    # Create a new list
    scripting_api.createNewGPList.restype = ctypes.POINTER(GPList)
    gp_list = scripting_api.createNewGPList()

    # Write all gp to the gp list
    for gp in gpar:
        if gp['ptype'] == 'real':
            gp_type = ctypes.c_int(1)
        elif gp['ptype'] == 'integer':
            gp_type = ctypes.c_int(2)
        elif gp['ptype'] == 'text':
            gp_type = ctypes.c_int(3)
        else:
            raise AMESimError("amewritegp", "Unknown type '{}' for parameter. "
                                            "Supported types are 'real', 'integer', 'text'".format(gp['ptype']))

        ret_code = scripting_api.createGP(gp_list, ctypes.byref(gp_type),
                                          ctypes.c_char_p(gp['pname'].encode('utf-8')),
                                          ctypes.c_char_p(gp['ptitle'].encode('utf-8')),
                                          ctypes.c_char_p(gp['pvalue'].encode('utf-8')),
                                          ctypes.c_char_p(gp['punit'].encode('utf-8')),
                                          ctypes.c_char_p(gp['pmin'].encode('utf-8')),
                                          ctypes.c_char_p(gp['pmax'].encode('utf-8')),
                                          ctypes.c_char_p(gp['pdef'].encode('utf-8')),
                                          ctypes.c_char_p(gp['pcirscope'].encode('utf-8')),
                                          ctypes.c_char_p(gp['pdatapath'].encode('utf-8')),
                                          ctypes.c_int(len(gp['penum_strings'])),
                                          ctypes.c_char_p("\n".join(gp['penum_strings']).encode('utf-8')))

        # Return false if error encountered
        if ret_code != 0:
            scripting_api.freeGPList(gp_list)
            return False

    # Write the gp list
    # scripting API expects a UTF8 encoding string but note that
    # currently, GP C API uses C function fopen to read the file and so only accept locale's encoding characters
    ret_code = scripting_api.writeGPList(gp_list, ctypes.c_char_p(sys_name_only.encode("utf8")),
                                         ctypes.c_char_p(sys_path.encode("utf8")))
    scripting_api.freeGPList(gp_list)

    if ret_code == 0:
        return True
    else:
        return False


class BatchStruct(ctypes.Structure):
    pass


class BatchParamStruct(ctypes.Structure):
    pass


def amegetbatch(sys_name):
    """
   amegetbatch Read the batch configuration (.sad) file of an Amesim model.

   batch_cfg = amegetbatch(sys_name)
         reads the batch configuration of the model sys_name and returns
         it in batch_cfg.

   sys_name : a complete path or just the name of the system in case the
         system is placed in the current working directory.

   batch_cfg  : a dictionary that contains the following key-value pairs:
      - type  : 'range' or 'set'
      - param : a list of dictionaries of parameters; some keys of this
                dictionary are different between 'range' and 'set' type
        common keys:
            - type : 'real' or 'int' or 'text'
            - name :  name of parameter
        'range' type keys:
            - value : value of parameter (as a character string)
            - step  : step value (as a character string)
            - below : number of steps below the value
            - above : number of steps above the value
        'set' type key:
            - set   : list of values for each user-defined data set
                      (as a character string)

   See also ameputbatch, amerunbatch.

   Copyright (c) 2016 Siemens Industry Software NV
   """

    # Get the max size length for batch param fields
    # and the values of the batch and param types
    param_max_len = ctypes.c_int()
    scripting_api.amebatch_get_param_max_len.restype = None
    scripting_api.amebatch_get_param_max_len(ctypes.byref(param_max_len))
    batch_range_type = ctypes.c_int()
    batch_set_type = ctypes.c_int()
    param_real_type = ctypes.c_int()
    param_int_type = ctypes.c_int()
    param_text_type = ctypes.c_int()
    scripting_api.amebatch_get_enum_values.restype = None
    scripting_api.amebatch_get_enum_values(ctypes.byref(batch_range_type), ctypes.byref(batch_set_type),
                                           ctypes.byref(param_real_type), ctypes.byref(param_int_type),
                                           ctypes.byref(param_text_type))

    # Output parameters
    batch_cfg = {}
    sys_name_only, sys_path = ameextractsysnameandpath(sys_name)

    # Read the batch file
    batch_ptr = ctypes.pointer(BatchStruct())
    if scripting_api.amebatch_read_batch(ctypes.c_char_p(sys_name_only.encode('utf8')),
                                         ctypes.c_char_p(sys_path.encode('utf8')),
                                         ctypes.byref(batch_ptr)) != 0:
        raise AMESimError('amegetbatch',
                          'cannot read the batch configuration(.sad) file of system "{}"'.format(sys_name_only))

    # Get the batch type
    batch_type = ctypes.c_int()
    if scripting_api.amebatch_get_batch_type(batch_ptr, ctypes.byref(batch_type)) != 0:
        raise AMESimError('amegetbatch', 'cannot read the batch type of system "{}"'.format(sys_name_only))

    # Set the type of output batch
    if batch_type.value == batch_range_type.value:
        batch_cfg['type'] = 'range'
    elif batch_type.value == batch_set_type.value:
        batch_cfg['type'] = 'set'
        batch_nb_sets = ctypes.c_int()
        if scripting_api.amebatch_get_batch_nb_sets(batch_ptr, ctypes.byref(batch_nb_sets)) != 0:
            raise AMESimError('amegetbatch',
                              'cannot read the total number of batch sets of system "{}"'.format(sys_name_only))

    # Get the number of parameters
    batch_nb_params = ctypes.c_int()
    if scripting_api.amebatch_get_batch_nb_param(batch_ptr, ctypes.byref(batch_nb_params)) != 0:
        raise AMESimError('amegetbatch',
                          'cannot read the total number of batch_cfg parameters of system "{}"'.format(sys_name_only))

    # Specify the return types of ctypes functions that return anything
    # other than integer, otherwise strange crashes may occur
    scripting_api.amebatch_free_batch.restype = None
    scripting_api.amebatch_free_param.restype = None

    batch_cfg['param'] = []

    # Get each param
    param_type = ctypes.c_int()
    param_name = ctypes.create_string_buffer(param_max_len.value)
    param_value = ctypes.create_string_buffer(param_max_len.value)
    param_step = ctypes.create_string_buffer(param_max_len.value)
    param_below = ctypes.c_int()
    param_above = ctypes.c_int()
    for param_idx in range(1, batch_nb_params.value + 1):
        param_ptr = ctypes.pointer(BatchStruct())
        if scripting_api.amebatch_get_batch_param(batch_ptr, ctypes.c_int(param_idx), ctypes.pointer(param_ptr)) != 0:
            raise AMESimError('amegetbatch',
                              'cannot read batch parameter number {} of system "{}"'.format(param_idx, sys_name_only))

        param_set = []
        if batch_type.value == batch_range_type.value:
            ret_code = scripting_api.amebatch_read_range_param(param_ptr,
                                                               ctypes.byref(param_type),
                                                               param_name,
                                                               param_value,
                                                               param_step,
                                                               ctypes.byref(param_below),
                                                               ctypes.byref(param_above),
                                                               None)
        elif batch_type.value == batch_set_type.value:
            ret_code = scripting_api.amebatch_read_set_param(param_ptr, ctypes.byref(param_type), param_name,
                                                             ctypes.byref(ctypes.c_int()))
            if ret_code == 0:
                for set_idx in range(1, batch_nb_sets.value + 1):
                    ret_code = scripting_api.amebatch_read_set_param_value(batch_ptr, ctypes.c_int(param_idx),
                                                                           ctypes.c_int(set_idx), param_value,
                                                                           ctypes.byref(ctypes.c_int()))
                    if ret_code == 0:
                        param_set.append(param_value.value.decode('utf8'))
                    else:
                        break

        scripting_api.amebatch_free_param(param_ptr)

        # Abort if any error has occurred
        if ret_code != 0:
            scripting_api.amebatch_free_batch(batch_ptr)
            raise AMESimError('amegetbatch',
                              'cannot read values of batch parameter number {} of system "{}"'.format(param_idx,
                                                                                                      sys_name_only))
        else:
            param = {'name': param_name.value.decode('utf8')}

            if batch_type.value == batch_range_type.value:
                param['value'] = param_value.value.decode('utf8')
                param['step'] = param_step.value.decode('utf8')
                param['below'] = param_below.value
                param['above'] = param_above.value
            elif batch_type.value == batch_set_type.value:
                param['set'] = param_set

            batch_cfg['param'].append(param)

    # Free the batch structure
    scripting_api.amebatch_free_batch(batch_ptr)

    return batch_cfg


def ameputbatch(sys_name, batch_cfg):
    """
   ameputbatch Write the batch configuration (.sad) file of an Amesim model.

   ret_stat = ameputbatch(sys_name, batch_cfg)
         writes the batch configuration file of the model sys_name from
         batch_cfg. The configuration file is written only if batch_cfg
         contains the required fields.

   sys_name : a complete path or just the name of the system in case the
         system is placed in the current working directory.

   batch_cfg  : a dictionary that contains the following key-value pairs:
      - type  : 'range' or 'set'
      - param : a list of dictionaries of parameters; some keys of this
                dictionary are different between 'range' and 'set' type
        common keys:
            - type : 'real' or 'int' or 'text'
            - name :  name of parameter
        'range' type keys:
            - value : value of parameter (as a character string)
            - step  : step value (as a character string)
            - below : number of steps below the value
            - above : number of steps above the value
        'set' type key:
            - set   : list of values for each user-defined data set
                      (as a character string)

   ret_stat : returned status, True for success

   See also ameputbatch, amerunbatch.

   Copyright (c) 2016 Siemens Industry Software NV
   """

    def isnumber(s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    if not isinstance(sys_name, str):
        raise AMESimError('ameputbatch', 'the first argument must be a text string')

    if not isinstance(batch_cfg, dict):
        raise AMESimError('ameputbatch', 'the second argument must be a dictionary')

    # Check that batch dictionary is consistent
    if 'type' not in batch_cfg or \
            not (batch_cfg['type'] == 'range' or batch_cfg['type'] == 'set'):
        raise AMESimError('ameputbatch', 'the value of "type" of the batch dictionary is not correctly set')

    # Check common parameter fields
    if 'param' not in batch_cfg or not isinstance(batch_cfg['param'], list):
        raise AMESimError('ameputbatch', 'the value of "param" of the batch dictionary is not correctly set')

    # Check each parameter
    # and do conversions if necessary
    for param in batch_cfg['param']:

        if 'name' not in param or not isinstance(param['name'], str):
            raise AMESimError('ameputbatch', 'the value of "name" of the "param" batch dictionary is not correctly set')

        # Check specific parameter fields
        if batch_cfg['type'] == 'range':
            if 'value' not in param or \
                    not (isinstance(param['value'], str) or isnumber(param['value'])):
                raise AMESimError('ameputbatch',
                                  'the value of "value" of the "param" batch dictionary is not correctly set')
            param['value'] = str(param['value'])
            if 'step' not in param or \
                    not (isinstance(param['step'], str) or isnumber(param['step'])):
                raise AMESimError('ameputbatch',
                                  'the value of "step" of the "param" batch dictionary is not correctly set')
            param['step'] = str(param['step'])
            if 'below' not in param or \
                    not isnumber(param['below']):
                raise AMESimError('ameputbatch',
                                  'the value of "below" of the "param" batch dictionary is not correctly set')
            param['below'] = int(param['below'])
            if 'above' not in param or \
                    not isnumber(param['above']):
                raise AMESimError('ameputbatch',
                                  'the value of "above" of the "param" batch dictionary is not correctly set')
            param['above'] = int(param['above'])
        elif batch_cfg['type'] == 'set':
            if 'set' not in param or not isinstance(param['set'], list) or len(param['set']) < 1:
                raise AMESimError('ameputbatch',
                                  'the value of "set" of the "param" batch dictionary is not correctly set')

    # Check if all sets have the same size
    # and convert each value to string
    if batch_cfg['type'] == 'set':
        batch_nb_sets = len(batch_cfg['param'][0]['set'])
        for param in batch_cfg['param']:
            if len(param['set']) != batch_nb_sets:
                raise AMESimError('ameputbatch',
                                  'not all "set" lists of the "param" batch dictionary have the same size')
            # convert all items to string
            param['set'][:] = [str(i) for i in param['set']]

    # Get the values of the batch and param types
    batch_range_type = ctypes.c_int()
    batch_set_type = ctypes.c_int()
    param_real_type = ctypes.c_int()
    param_int_type = ctypes.c_int()
    param_text_type = ctypes.c_int()
    param_default_type = ctypes.c_int(0)
    scripting_api.amebatch_get_enum_values.restype = None
    scripting_api.amebatch_get_enum_values(ctypes.byref(batch_range_type), ctypes.byref(batch_set_type),
                                           ctypes.byref(param_real_type), ctypes.byref(param_int_type),
                                           ctypes.byref(param_text_type))

    # Set the batch type
    if batch_cfg['type'] == 'range':
        batch_type = batch_range_type
    elif batch_cfg['type'] == 'set':
        batch_type = batch_set_type

    # Create a batch structure
    batch_ptr = ctypes.pointer(BatchStruct())
    scripting_api.amebatch_create_batch(batch_type, ctypes.byref(batch_ptr))

    # Add  the rest of sets for 'set' type batch
    if batch_cfg['type'] == 'set':
        scripting_api.amebatch_add_batch_set(batch_ptr, batch_nb_sets)

    # Specify the return types of ctypes functions that return anything
    # other than integer, otherwise strange crashes may occur
    scripting_api.amebatch_free_batch.restype = None
    scripting_api.amebatch_free_param.restype = None

    # Create the parameters
    for param_idx, param in enumerate(batch_cfg['param'], start=1):
        # Set the param type
        param_type = param_default_type
        param_ptr = ctypes.pointer(BatchParamStruct())

        if batch_cfg['type'] == 'range':
            # C++ implementation uses std::string decoded as UTF-8 by the application
            ret_code = scripting_api.amebatch_create_range_param(param_type,
                                                                 ctypes.c_char_p(param['name'].encode('utf8')),
                                                                 ctypes.c_char_p(param['value'].encode('utf8')),
                                                                 ctypes.c_char_p(param['step'].encode('utf8')),
                                                                 ctypes.c_int(param['below']),
                                                                 ctypes.c_int(param['above']),
                                                                 ctypes.pointer(param_ptr))

        elif batch_cfg['type'] == 'set':
            ret_code = scripting_api.amebatch_create_set_param(param_type, ctypes.c_char_p(param['name'].encode('utf8'))
                                                               , ctypes.pointer(param_ptr))

        # Append the parameter to the batch structure
        if scripting_api.amebatch_append_batch_param(batch_ptr, param_ptr) != 0:
            scripting_api.amebatch_free_param(param_ptr)
            scripting_api.amebatch_free_batch(batch_ptr)
            raise AMESimError('ameputbatch',
                              'cannot append the batch parameter number {} to the batch structure'.format(param_idx))

        if batch_cfg['type'] == 'set':
            if ret_code == 0:
                for set_idx, set_val in enumerate(param['set'], start=1):
                    ret_code = scripting_api.amebatch_modify_set_param(batch_ptr, ctypes.c_int(param_idx),
                                                                       ctypes.c_int(set_idx),
                                                                       ctypes.c_char_p(set_val.encode('utf8')))
                    if ret_code != 0:
                        break

        # Abort if any error has occurred
        if ret_code != 0:
            scripting_api.amebatch_free_batch(batch_ptr)
            raise AMESimError('ameputbatch', 'cannot create the batch parameter number {}'.format(param_idx))

        scripting_api.amebatch_free_param(param_ptr)

    sys_name_only, sys_path = ameextractsysnameandpath(sys_name)

    # Write the the batch configuration file
    if scripting_api.amebatch_write_batch(ctypes.c_char_p(sys_name_only.encode('utf8')),
                                          ctypes.c_char_p(sys_path.encode('utf8')), batch_ptr) != 0:
        raise AMESimError('ameputbatch',
                          'cannot write the batch configuration(.sad) file of system "{}"'.format(sys_name_only))

    scripting_api.amebatch_free_batch(batch_ptr)

    return True


def amepreparebatchrun(sys_name):
    """
   amepreparebatchrun Write the files needed to perform a batch run.

   ret_stat = AMEPREPAREBATCHRUN(sys_name)
         writes the batch index files (*.vl.i, *.param.i, *.data.i, ...)
         that are needed to perform a batch simulation of the model
         sys_name. The batch configuration (.sad) file must be written
         before calling this function.

   sys_name : a complete path or just the name of the system in case the
              system is placed in the current working directory.
   ret_stat : returned status, true for success, false if failure.

   See also amegetbatch, ameputbatch, amerunbatch.

   Copyright (c) 2016 Siemens Industry Software NV
   """

    sys_name_only, sys_path = ameextractsysnameandpath(sys_name)

    if scripting_api.amebatch_prepare_run(ctypes.c_char_p(sys_name_only.encode('utf8')),
                                          ctypes.c_char_p(sys_path.encode('utf8'))) != 0:
        raise AMESimError('amepreparebatchrun',
                          'cannot create the files needed for batch simulation of system "{}"'.format(sys_name_only))

    return True


def amegetbatchrunstatus(sys_name):
    """
   amegetbatchrunstatus Get the last simulated runs of a batch.

   runs = amegetbatchrunstatus(sys_name) returns the last
         simulated batch runs of the model sys_name.

   sys_name : a complete path or just the name of the system in case the
              system is placed in the current working directory.
   runs     : a list containing the number ids of the last simulated
              batch runs.

   See also amegetbatch, ameputbatch, amerunbatch.

   Copyright (c) 2016 Siemens Industry Software NV
   """

    sys_name_only, sys_path = ameextractsysnameandpath(sys_name)

    runs_read = ctypes.POINTER(ctypes.c_int)()  # NULL pointer
    runs_size = ctypes.c_int()

    if scripting_api.amebatch_get_run_status(ctypes.c_char_p(sys_name_only.encode('utf8')),
                                             ctypes.c_char_p(sys_path.encode('utf8')),
                                             ctypes.byref(runs_size), ctypes.byref(runs_read)) != 0:
        raise AMESimError('amegetbatchrunstatus', 'cannot read the batch runs of system "{}"'.format(sys_name_only))

    runs = [runs_read[ii] for ii in range(runs_size.value)]
    scripting_api.amebatch_free_run_status.restype = None
    scripting_api.amebatch_free_run_status(runs_read)

    return runs


def amerunbatch(sys_name, sim_opt=None, activate_runs='all', nb_parallel_runs=1):
    """
   amerunbatch Start a batch simulation.

   [ret_stat, msg] = amerunbatch(sys_name)
         starts a batch simulation of model sys_name.

   [ret_stat, msg] = amerunbatch(sys_name, sim_opt)
         starts a batch simulation using the simulation options from
         sim_opt.

   [ret_stat, msg] = amerunbatch(sys_name, sim_opt, activate_runs)
         starts a batch simulation using the simulation options from
         sim_opt, activating only the runs specified in activate_runs.

   [ret_stat, msg] = amerunbatch(sys_name, sim_opt, 'all', 4)
         starts a batch simulation using the simulation options from
         sim_opt, activating all runs and using 4 parallel processes.

   sys_name  : a complete path or just the sys_name of the system in case
         the system is placed in the current working directory.
   sim_opt (optional) : a SimOptions instance that contains the simulation
         options. Check documentation of amegetsimopt for complete description.
   activate_runs (optional) : a list containing numeric values for
         each run. A value of 0 means the run is deactivated and will not
         be simulated; any other value means the run is activated. If the
         size of the activate_runs list is lower than the number of runs
         in batch, then the remaining unspecified runs will be activated.
   nb_parallel_runs (optional): maximum number of simulation processes to
         use.
   ret_stat        : returned status, true for success, false if failure.
   msg             : run details message

   See also amegetbatch, ameputbatch, amegetbatchrunstatus.

   Copyright (c) 2016 Siemens Industry Software NV
   """

    ###################################
    # Check number of input arguments #
    ###################################
    if type(activate_runs) is not list and activate_runs != 'all':
        raise AMESimError('amerunbatch', 'The third argument must be either a list or the string "all".')

    # Extract system name and path from the string name
    sys_name_only, sys_path = ameextractsysnameandpath(sys_name)

    # Read the batch file to handle activate_runs
    batch_ptr = ctypes.pointer(BatchStruct())
    ret_code = scripting_api.amebatch_read_batch(ctypes.c_char_p(sys_name_only.encode('utf8')),
                                                 ctypes.c_char_p(sys_path.encode('utf8')),
                                                 ctypes.byref(batch_ptr))

    if ret_code == 0:
        # Set the active runs only if activate_runs argument was provided
        # otherwise all runs will be activated
        if activate_runs != 'all':
            ret_code = scripting_api.amebatch_set_active_runs(batch_ptr,
                                                              (ctypes.c_int * len(activate_runs))(*activate_runs),
                                                              ctypes.c_int(len(activate_runs)))

        # Write the the batch configuration file
        if ret_code == 0:
            ret_code = scripting_api.amebatch_write_batch(ctypes.c_char_p(sys_name_only.encode('utf8')),
                                                          ctypes.c_char_p(sys_path.encode('utf8')),
                                                          batch_ptr)

        # Free the batch structure
        scripting_api.amebatch_free_batch.restype = None
        scripting_api.amebatch_free_batch(batch_ptr)

    if ret_code != 0:
        raise AMESimError('amerunbatch', 'cannot set the active runs of system "{}"'.format(sys_name_only))

    # Write the simulation options
    if sim_opt is not None:
        ameputsimopt(sys_name, sim_opt)

    # Write the files needed for batch simulation
    amepreparebatchrun(sys_name)

    _print('Starting batch simulation ...')
    try:
        bytes_msg = subprocess.check_output(
            'STDSIMBatch -simuname ' + '"' + sys_path + '/' + sys_name_only + '"' + ' -processes ' + str(
                nb_parallel_runs),
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            shell=True)
    except subprocess.CalledProcessError as e:
        ret_val = e.returncode
        bytes_msg = e.output
    else:
        ret_val = 0

    _print('... simulation completed')

    if ret_val == 0:
        ret_stat = True
    else:
        ret_stat = False
    
    msg = _decodeBytes(bytes_msg)
    
    return [ret_stat, msg]


def ameextractsysnameandpath(filename):
    r""" ameextractsysnameandpath extracts the system name and path from
   the filename string.

   Exemples of input strings that can be processed:
   C:\Data\AMETest\v1400\3DMeca\4Bars
   C:/Data/AMETest/v1400/3DMeca/4Bars_.gp
   C:/Data/AMETest/v1400/3DMeca/4Bars_.sad
   /home/user/4Bars.ame
   4Bars
   4Bars_.gp
   4Bars_.sad
   4Bars.ame

   If input strings contains only the filename or the system name,
   the current working directory path is returned as path."""

    if not isinstance(filename, str):
        raise AMESimError('ameextractsysnameandpath', 'the argument must be a text string')

    gpfilename = filename.replace('\\', '/')
    sep_pos = gpfilename.rfind('/')

    if sep_pos < 0:
        syspath = os.getcwd().replace('\\', '/')
    else:
        syspath = gpfilename[: sep_pos]
        gpfilename = gpfilename[sep_pos + 1:]

    ext_pos = gpfilename.rfind('_.')

    if ext_pos < 0:
        ext_pos = gpfilename.rfind('.ame')

    if ext_pos < 0:
        sysname = gpfilename
    else:
        sysname = gpfilename[:ext_pos]

    return sysname, syspath


def amegetvar(R, S, wantedtitle):
    """ amegetvar Select variables from AMESim result list

        [R1, S1]=amegetvar(R, S, 'title') extracts the AMESim
        results from R and S that match 'title'
        R and S were read with ameloadt.

        Examples of usage:

            [R,S] = ameloadt('testsystem')
            time  = amegetvar(R,S,'time [s]')
            xp    = amegetvar(R,S,'HJ000_1 rod displacement [m]')

            [R,S] = ameloadt('testsystem')
            time  = amegetvar(R,S,'time [s]')
            pressures = amegetvar(R,S,'*[bar]*')

    See also ameloadt

    Copyright (C) 2019 by Siemens Industry Software NV """

    _printError('Warning: "amegetvar" function is deprecated. Consider using "ameloadvarst"')

    R_out = []
    S_out = []
    foundvars = []

    # Simply loop through the S vector and set
    # foundvars to the indices that match our search string

    for i in range(len(S)):
        if amestrmatch(S[i].strip(), wantedtitle.strip()):
            foundvars.append(i)
            R_out.append(R[i])
            S_out.append(S[i].strip())

    return [R_out, S_out]


def fx2ame(*args):
    """ fx2ame Save table in file for 1-D interpolation AMESim function

    fx2ame(X,Y,'FILENAME') create formated file (FILENAME) for 1-D
    interpolation used by table1d AMESim function. X and Y are lists
    of number of same length where Y is the values of a function of X
    (Y=function(X))

    When invoked with no FILENAME argument, fx2ame write result on the
    standard output (the screen).

    Copyright (C) 2019 by Siemens Industry Software NV """

    ########################################
    # Check the number of input paramaters #
    ########################################

    if len(args) > 3 or len(args) < 2:
        raise AMESimError('fx2ame', 'fx2ame requires two or three arguments')
    x = args[0]
    y = args[1]

    ##########################################
    # Make sure we have a one dimension list #
    ##########################################

    if not isinstance(x, list):
        raise AMESimError('fx2ame', 'x must be a one dimension list')

    if not isinstance(y, list):
        raise AMESimError('fx2ame', 'y must be a one dimension list')

    if len(x) != len(y):
        raise AMESimError('fx2ame', 'x and y must have the same length')

    for i in range(len(x)):
        if not isinstance(x[i], (int, float)):
            raise AMESimError('fx2ame', 'x must contain only numbers')
        if not isinstance(y[i], (int, float)):
            raise AMESimError('fx2ame', 'y must contain only numbers')

    #####################################################
    # Open output file or standard output (the screen)  #
    #####################################################
    if len(args) == 2:
        for i in range(len(x)):
            _print('%e %e' % (x[i], y[i]))
    else:
        filename = args[2]
        try:
            fid = open(filename, 'w')
        except IOError as e:
            raise AMESimError('fx2ame', 'unable to write in ' + filename) from e
        fid.write('# Table format: 1D\n')
        for i in range(len(x)):
            fid.write('%e %e\n' % (x[i], y[i]))
        fid.close()
    return


def ameloadj(*args):
    """
    ameloadj Load AMESim .jac format jacobian files.

    [A, B, C, D, x, u, y, t, xvals] = ameloadj('system_.jac0') extracts
    continuous state-space matrix (A, B, C, D) about the current point at time (t)
    computed by AMESim using numerical perturbations. In X, U, Y it returns the
    titles of states, input, output variables. xvals contains the values of the
    free states variables at the point of linearization, available for models
    crated with AMESim 4.2 or later.

    In matrix or state-space form, the equations can be written as:

        xdot = A x + B u
        y    = C x + D u

    where u is a vector of control inputs, x is a state vector, y is a vector
    of observer inputs.

    [A, B, C, D, x, u, y, t, xvals] = ameloadj() asks for the name of the system.

    [A, B, C, D, x, u, y, t, xvals] = ameloadj('system',jac_id) loads the
    Jacobian specified by jac_id.

    [A, B, C, D, x, u, y, t, xvals] = ameloadj('system',jac_id,run_id) loads the
    jac_id Jacobian from the batch run specified by run_id.
    Note that jac_id starts at 0, while batch run_id starts from 1.

    A, B, C, D, x, y, xvals are lists. These lists can be considered as matrices when they
    are lists of lists. Then the following representation is chosen

    A= [[  ,      ,    ],
        [  ,      ,    ],
        ..............
        [  ,      ,    ]]
    Number of lines = len(A)
    Number of columns = len(A[0])
    element A(i,j) = A[i+1][j+1]

    The utility function transposelist can be used to choose the other representation.

    See also ameloadt, transposelist

    Copyright (C) 2019 by Siemens Industry Software NV
    """

    EPSILON_CMPLX = 1.0e-7

    #####################################################
    # Constants related to Unique Identifier management #
    #####################################################
    strip_unique_identifier = True
    unique_identifier_keyword = 'Data_Path'
    unique_identifier_search_regex = ' ' + unique_identifier_keyword + r'=.*@\S*'

    ###################################
    # Check number of input arguments #
    ###################################
    if len(args) > 3:
        raise AMESimError('ameloadj', 'too many input arguments')

    #######################
    # Ask for system name #
    #######################
    if len(args) == 0:
        inputname = openmyfile()
    else:
        inputname = args[0]

    if (inputname == '') or (inputname == ()):
        raise AMESimError('ameloadj', 'command canceled')
    inputname = inputname.strip()

    # Extract system name (sname) from the string inputname
    sname = getSystemName(inputname)

    ########################################################################
    # Explode the system file to create some temporary files (if required) #
    ########################################################################

    if not os.path.isfile(sname + '_.cir'):
        os.system('AMELoad ' + sname)
        explode = 1
    else:
        explode = 0

    ############################
    # Read LA time in .LA file #
    ############################
    try:
        fid = open(sname + '_.la')
    except IOError as e:
        raise AMESimError('ameloadj', 'unable to read in ' + sname + '_.la') from e

    # Read the number of linearization times
    match_integer = re.compile(r'(\d+) .*').match(fid.readline().strip())
    if not match_integer:
        raise AMESimError('ameloadj', sname + '_.la file does not begin with the number of linearization time')
    ntime = int(match_integer.group(1))

    if ntime == 0:
        raise AMESimError('ameloadj', 'there is no linearization time for this system')

    # Read theoretical LA time
    for i in range(ntime):
        fid.readline()

    # If a Jacobian number is specified in the argument list
    # use it
    if len(args) == 2:
        jnumber = args[1]
        inputname = sname + '_.jac' + str(jnumber)

    # If a runid (batch number) is specified, use it
    if len(args) == 3:
        jnumber = args[1]
        runid = args[2]
        inputname = sname + '_.jac' + str(jnumber) + '.' + str(runid)

    ##################################
    # Ask for a Jacobian file number #
    ##################################
    if (inputname.find('_.jac') == -1) or (not os.path.isfile(inputname)):
        # Look for .jac file
        jname = sname + '_.jac'
        jacfiles = []
        latime = []
        nof = []
        for i in range(ntime):
            if os.path.isfile(jname + str(i)):
                jacfiles.append(jname + str(i))

                # Read real LA time
                try:
                    fid1 = open(jname + str(i), 'r')
                except IOError as e:
                    raise AMESimError('ameloadj', f'unable to read in {jname}{i}') from e
                dataline = fid1.readline()
                fid1.close()
                dataline.strip()
                datalist = dataline.split()
                latime.append(float(datalist[3]))
                nof.append(i)

        # Ask for .jac file to read
        if len(nof) == 1:
            jname = jname + str(nof[0])
        elif len(nof) > 1:
            _print('List of Jacobian files for your system:')
            for i in range(len(nof)):
                _print(jacfiles[i] + ' at t = ' + str(latime[i]) + ' [s] ..........' + str(nof[i]))
            choosednumber = input('Your choice : ').strip()
            jname = jname + choosednumber
        else:
            fid.close()
            raise AMESimError('ameloadj', 'there is no Jacobian file for the system')

    else:
        jname = inputname

    #########################################################
    # Initialize state, control and observers string matrix #
    #########################################################

    # Read fixed states from .la file
    nfs = _read_integer_counter(fid)  # Number of fixed states
    fsi = _read_integer_values(fid, nfs)

    # Read control variables
    ncv = _read_integer_counter(fid)  # Number of control variables
    cvi = _read_integer_values(fid, ncv)

    # Read observer variables
    nov = _read_integer_counter(fid)  # Number of observer variables
    ovi = _read_integer_values(fid, nov)

    fid.close()

    ##############################
    # Read free state vector (x) #
    ##############################
    try:
        fid = open(sname + '_.state', 'rb')  # open in binary mode, decode later to support legacy encoding
    except IOError as e:
        raise AMESimError('ameloadj', 'unable to read in ' + sname + '_.state') from e

    x = [_decodeBytes(l) for l in fid.readlines()] # x is the list of lines from the file
    fid.close()
    for i in range(len(x)):
        x[i] = x[i].strip()
        # Strip Unique Identifier if required
        if strip_unique_identifier and x[i].find(unique_identifier_keyword) != -1:
            x[i] = re.sub(unique_identifier_search_regex, "", x[i])

    # Look for free state
    X = []
    if nfs:
        statevect = list(range(len(x)))
        freevect = []
        for i in statevect:
            if i not in fsi:
                freevect.append(i)

        for i in freevect:
            X.append(x[i])
    else:
        X = x

    ###################################################
    # Create control (u) and observer (y) string list #
    ###################################################
    try:
        fid = open(sname + '_.var', 'rb')  # open in binary mode, decode later to support legacy encoding
    except IOError as e:
        raise AMESimError('ameloadj', 'unable to read in ' + sname + '_.var') from e

    var = [_decodeBytes(l) for l in fid.readlines()]
    fid.close()
    for i in range(len(var)):
        var[i] = var[i].strip()
        # Strip Unique Identifier if required
        if strip_unique_identifier and var[i].find(unique_identifier_keyword) != -1:
            var[i] = re.sub(unique_identifier_search_regex, "", var[i])

    U = []
    Y = []
    for i in cvi:
        U.append(var[i])  # Control variables name string list
    for i in ovi:
        Y.append(var[i])  # Observer variables name string list

    #####################
    # Read state matrix #
    #####################

    # Open Jacobian file
    try:
        fid = open(jname, 'r')
    except OSError as e:
        raise AMESimError('ameloadj', 'unable to read in ' + jname) from e

    read_line = fid.readline().strip()
    if read_line == '':
        fid.close()
        raise AMESimError('ameloadj', 'check first line of ' + jname)
    nfree = int(read_line.split()[0])
    ncontrol = int(read_line.split()[1])  # Number of control inputs
    nobserve = int(read_line.split()[2])  # Number of outputs
    T = float(read_line.split()[3])  # Time

    A = []
    if nfree != 0:
        if X:
            X = X[:nfree]  # Suppress implicit states

        for i in range(nfree):
            read_line = fid.readline().strip()
            templist = read_line.split()
            A.append([])
            for j in range(nfree):
                A[i].append(float(templist[j]))
    B = []
    B0 = []
    if (nfree != 0) and (ncontrol != 0):
        for i in range(nfree):
            read_line = fid.readline().strip()
            templist = read_line.split()
            B0.append([])
            for j in range(ncontrol):
                B0[i].append(float(templist[j]))
    B.append(B0)
    C = []
    if (nfree != 0) and (nobserve != 0):
        for i in range(nobserve):
            read_line = fid.readline().strip()
            templist = read_line.split()
            C.append([])
            for j in range(nfree):
                C[i].append(float(templist[j]))
    D = []
    D0 = []
    if (ncontrol != 0) and (nobserve != 0):
        for i in range(nobserve):
            read_line = fid.readline().strip()
            templist = read_line.split()
            D0.append([])
            for j in range(ncontrol):
                D0[i].append(float(templist[j]))
    D.append(D0)
    B0 = []
    D0 = []
    line_nil = fid.readline().strip()
    state_values = []
    index_nil_pot = 0
    if line_nil[:23] == 'Index of nilpotency is ':
        index_nil_pot = int(line_nil[23:])
        for iter_var in range(index_nil_pot):
            if (nfree != 0) and (ncontrol != 0):
                for i in range(nfree):
                    read_line = fid.readline().strip()
                    templist = read_line.split()
                    B0.append([])
                    for j in range(ncontrol):
                        B0[i].append(float(templist[j]))
            B.append(B0)
            B0 = []

            if (nobserve != 0) and (ncontrol != 0):
                for i in range(nobserve):
                    read_line = fid.readline().strip()
                    templist = read_line.split()
                    D0.append([])
                    for j in range(ncontrol):
                        D0[i].append(float(templist[j]))
            D.append(D0)
            D0 = []
    else:
        if nfree > 0:
            state_values.append(float(line_nil))
    if nfree > 0:
        while 1:
            read_line = fid.readline()
            if not read_line:
                break

            state_values.append(float(read_line.strip()))

    fid.close()
    # To do ? See if we must transpose B[i]

    ##########################
    # Printout some comments #
    ##########################
    _print(' ')
    _print(' * Linearization time = ' + str(T) + ' [s]')
    _print(' ')

    if line_nil[:23] == 'Index of nilpotency is ':
        _print(' * Index of nilpotency = {}'.format(index_nil_pot))

    if nfree == 0:
        _print(' * There is no state variable')
    else:
        _print(' * There are {} free state variables'.format(nfree))
        for e in X:
            _print(e)
        _print('\n')

    if ncontrol == 0:
        _print(' * There is no control input')
    else:
        _print(' * There are {} control outputs'.format(ncontrol))
        for e in U:
            _print(e)
        _print('\n')

    if nobserve == 0:
        _print(' * There is no observer output', )
    else:
        _print(' * There are {} observer outputs'.format(nobserve))
        for e in Y:
            _print(e)
        _print('\n')

    ############################################
    # Delete the temporyra files of the system #
    ############################################
    if explode:
        os.system('AMEClean -y ' + sname)

    ###############################################
    # Printout Eigenvalues, Damping and frequency #
    ###############################################
    try:
        import numpy as N
        import numpy.linalg as LA
        from math import cos, atan2, pi
        NewestLA = 1
    except ImportError:
        try:
            import Numeric as N
            import LinearAlgebra as LA
            from math import cos, atan2, pi
            NewestLA = 0
        except ImportError:
            _printError('Install numpy to compute the eigenvalues')
            return [A, B, C, D, X, U, Y, T, state_values]

    ArrayA = N.array(A) + 0j  # Force to complex to have complex eigenvalues
    if NewestLA:
        val = LA.eigvals(ArrayA)
    else:
        val = LA.eigenvalues(ArrayA)

    # Sort frequencies in ascending order of modulus
    wn = N.sort(abs(val))
    index_sort = N.argsort(abs(val))
    # Compute damping ratio
    z = []
    for i in range(len(val)):
        try:
            expr = -cos(atan2(complex(val[index_sort[i]]).imag, complex(val[index_sort[i]]).real))
        except ValueError:
            # On Sun/Solaris 8, atan2(0.,0.) raises an error with errno=EDOM.
            # See atan2(3M) man page.
            z.append(-1.0)
        else:
            z.append(expr)
    # Display eigenvalue analysis results
    _print('  Eigenvalue                   Damping ratio          Undamped freq. [Hz]')
    for i in range(len(val)):
        if abs(val[index_sort[i]].imag) > EPSILON_CMPLX * abs(val[index_sort[i]].real):
            _print('  %+-11.3f %+-11.3f*i     %-11.3f            %-11.3f\n' % (
                val[index_sort[i]].real, val[index_sort[i]].imag, z[i], wn[i] / (2 * pi)))
        else:
            _print('  %-11.3f                   %-11.3f            0\n' % (val[index_sort[i]].real, z[i]))

    return [A, B, C, D, X, U, Y, T, state_values]


def data2ame(*args):
    """
    data2ame Save data in a file readable by AMESim plot facility.

    Save data in file readable by AMESim using the "Load" facility
    on the pulldown menu of a plot.

    The format of the file is the same as the format using "export values"

    data2ame(xy, 'filename') saves data list of lists xy. xy is the size the
    number of points (len(xy[0]) by the number of variables (len(xy)). The first
    element of xy contains the x-values and the following contains the y-axes quantities.

    data2ame(x, y, 'filename') saves x-axis values (x) and y-axis values (y).
    x is of length the number of points, y is a list of lists of size the number
    of points (len(y[0])) by the number of y-axis quantities (len(y)).

    When invoked with no filename argument, data2ame writes the results on the
    standard output (the screen).

    See also ameloadt, transposelist, ame2data

    Copyright (C) 2019 by Siemens Industry Software NV
    """

    if len(args) > 3 or len(args) < 1:
        raise AMESimError('data2ame', 'data2ame requires one, two or three arguments')

    if len(args) < 2:
        xy = args[0]
        filename = ''
    elif isinstance(args[1], str):
        xy = args[0]
        filename = args[1]
    else:
        if isinstance(args[1][0], list):
            arg2 = args[1]
        else:
            arg2 = [args[1]]
        arg1 = args[0]
        if len(arg2[0]) != len(arg1):
            # if len(args[1][0]) == 1 and len(args[1]) == len(args[0]):
            # Tolerance if y is a vector
            raise AMESimError('data2ame', 'X and Y dimensions must agree')
        xy = [arg1]
        for e in arg2:
            xy.append(e)
        filename = ''

    if len(args) == 3:
        filename = args[2]

    ####################################################
    # Open output file or standard output (the screen) #
    ####################################################

    if filename == '':
        fid = sys.stdout
    else:
        try:
            fid = open(filename, 'w')
        except IOError as e:
            raise AMESimError('data2ame', 'unable to write in ' + filename) from e

    ########################
    # Write formatted data #
    ########################
    n = len(xy[0])
    m = len(xy)
    if m == 1:
        raise AMESimError('data2ame', 'the minimum number of y-axes quantites is one')

    # AMSim plot file header
    fid.write('# AMESim plot file format version: 2\n')
    fid.write('# ' + str(n) + ' rows\n')
    fid.write('# ' + str(m) + ' columns\n')

    # Data (one line per x-axis value)
    for i in range(n):
        for j in range(m):
            fid.write('%e ' % xy[j][i])
        fid.write('\n')

    ########################
    # Close file if needed #
    ########################

    if filename != '':
        fid.close()

    return


def fxy2ame(*args):
    """
    fxy2ame Save table in file for 2-D interpolation AMESim function.

    fxy2ame(x, y, z, 'filename') creates a formatted file (filename) for
    2-D interpolation used by table2d AMESim function. x and y are two lists
    of numbers, length(x) = n and length(y) = m.
    z must be of the form [[ (len(x)) ], [  (len(x) ], ...]
                           |______________________________|
                                       len(y)

    When invoked with no filename argument, fxy2ame writes the results on
    the standard output (the screen).

    See also fx2ame, transposelist.

    Copyright (C) 2019 by Siemens Industry Software NV
    """

    # #################################
    # Check number of input arguments #
    ###################################
    if len(args) > 4 or len(args) < 3:
        raise AMESimError('fxy2ame', 'fxy2ame requires three or four arguments')

    #########################################
    # Make sure x and y are lists of numbers #
    #########################################
    x = args[0]
    y = args[1]
    z = args[2]
    if not isinstance(x, list):
        raise AMESimError('fxy2ame', 'x must be a list of numbers')
    if not isinstance(x[0], (float, int)):
        raise AMESimError('fxy2ame', 'x must be a list of numbers')

    if not isinstance(y, list):
        raise AMESimError('fxy2ame', 'y must be a list of numbers')
    if not isinstance(y[0], (float, int)):
        raise AMESimError('fxy2ame', 'y must be a list of numbers')

    ###################
    # Test dimensions #
    ###################
    if not isinstance(z, list):
        raise AMESimError('fxy2ame', 'z must be a list of list')

    if not isinstance(z[0], list):
        raise AMESimError('fxy2ame', 'z must be a list of list')
    m = len(z)
    n = len(z[0])

    if len(x) != n:
        raise AMESimError('fxy2ame', 'x must have the same number of elements as each element of z')
    if len(y) != m:
        raise AMESimError('fxy2ame', 'y must have the same number of elements z')

    ####################################################
    # Open output file or standard output (the screen) #
    ####################################################
    if len(args) == 3:
        fid = sys.stdout
    else:
        filename = args[3]
        try:
            fid = open(filename, 'w')
        except IOError as e:
            raise AMESimError('fxy2ame', 'unable to write in ' + filename) from e
        fid.write('# Table format: 2D\n')

    ########################
    # Write formatted data #
    ########################
    # Number of x and y values
    fid.write('%i %i\n\n' % (n, m))

    maxlen = 6

    # x values
    for iter_var in range(len(x)):
        fid.write('%e ' % x[iter_var])
        if (iter_var + 1) - int((iter_var + 1) / maxlen) * maxlen == 0:  # Does the same as the rem function in Matlab
            fid.write('\n')

    fid.write('\n\n')

    # y values
    for iter_var in range(len(y)):
        fid.write('%e ' % y[iter_var])
        if (iter_var + 1) - int((iter_var + 1) / maxlen) * maxlen == 0:  # Does the same as the rem function in Matlab
            fid.write('\n')

    fid.write('\n\n')

    # z values (one line per x-axis value)
    for iter1 in range(len(y)):
        for iter2 in range(len(x)):
            fid.write('%e ' % z[iter1][iter2])
            if (iter2 + 1) - int((iter2 + 1) / maxlen) * maxlen == 0:  # Does the same as the rem function in Matlab
                fid.write('\n')
        fid.write('\n')

    fid.write('\n')

    ##########################
    # Close file if required #
    ##########################
    if len(args) == 4:
        fid.close()

    return


def tf2ame(*args):
    """
    tf2ame Save trasfer function in an external file readable by AMESim.

        Save transfer function:


        H(s) = NUM(s) / DEN(s)

    in an external file readable as an AMESim special submodel.

    NUM and DEN are lists containing the coefficients of the numerator and
    denominator in descending power of s.

    tf2ame(NUM, DEN, 'filename') saves the transfer function in the file
    'filename'.

    tf2ame(NUM, DEN) without third argument saves the transfer function in
    the file TRANSF.ssp

    See also ss2ame, ameloadj.

    Copyright (C) 2019 by Siemens Industry Software NV
    """

    ###################################
    # Check number of input arguments #
    ###################################
    if len(args) > 3 or len(args) < 2:
        raise AMESimError('tf2ame', 'tf2ame requires two or three arguments')

    numerator = args[0]
    denominator = args[1]

    # Check if denominator and numerator ar lists of numbers
    if not isinstance(numerator, list):
        raise AMESimError('tf2ame', 'numerator must be a list of numbers')
    if not isinstance(numerator[0], (float, int)):
        raise AMESimError('tf2ame', 'numerator must be a list of numbers')

    if not isinstance(denominator, list):
        raise AMESimError('tf2ame', 'denominator must be a list of numbers')
    if not isinstance(denominator[0], (float, int)):
        raise AMESimError('tf2ame', 'denominator must be a list of numbers')

    ####################
    # Open output file #
    ####################
    if len(args) == 2:
        filename = 'TRANSF.ssp'
    else:
        filename = args[2]

    try:
        fid = open(filename, 'w')
    except IOError as e:
        raise AMESimError('tf2ame', 'unable to write in ' + filename) from e

    ########################
    # Write formatted data #
    ########################
    nn = len(numerator)
    nd = len(denominator)
    fid.write('TRANSF "Continuous transfer function"\n')
    fid.write('%i numerator order \n' % (nn - 1))
    fid.write('%i denominator order \n' % (nd - 1))

    # Numerator
    for i in range(nn):
        fid.write('%.17e Numerator (s^%i)\n' % (numerator[i], nn - i - 1))

    # Denominator
    for i in range(nd):
        fid.write('%.17e Denominator (s^%i)\n' % (denominator[i], nd - i - 1))

    fid.close()
    return


def ss2ame(*args):
    """
    ss2ame Save state-space matrix system in an external file readable by AMESim.

    Save state-space system:

        xdot = A x + B u
        y    = C x + D u

    in an external file readable as an AMESim special submodel.

    ss2ame(A, B, C, D, 'filename', X) saves the state-space matrices A, B, C, D
    in the file 'filename' along with the values of the state variables X.

    ss2ame(A, B, C, D, 'filename) saves the state-space matrices A, B, C, D in
    the file 'filename'

    ss2ame(A, B, C, D) without fifth argument saves the matrices in the default
    file STATSP.ssp

    The matrices are represented by lists of the following form

    A= [[  ,      ,    ],
        [  ,      ,    ],
        ..............
        [  ,      ,    ]]


    Number of lines = len(A)
    Number of columns = len(A[0])
    element A(i,j) = A[i+1][j+1]

    The utility function transposelist can be used to choose the other representation.

    See also tf2ame, ameloadj, transposelist.

    Copyright (C) 2019 by Siemens Industry Software NV
    """

    ###################################
    # Check number of input arguments #
    ###################################
    if len(args) > 6 or len(args) < 4:
        raise AMESimError('ss2ame', 'ss2ame requires four, five or six arguments')
    A = args[0]
    B = args[1]
    C = args[2]
    D = args[3]
    abcdchk(A, B, C, D)

    ##################################
    # Check for a a 6th arg with the #
    # values of state variables      #
    ##################################
    xvals = []
    if len(args) == 6:
        inparg6 = args[5]
        if len(A) == len(inparg6):
            xvals = inparg6
        else:
            raise AMESimError('ss2ame', 'the state vector (6th argument) has not the same size as the A matrix')

    ####################################
    # How many states, inputs, outputs #
    ####################################
    # Number of states
    ns = len(A)

    # Number of inputs
    if len(D) == 0:
        ni = len(B[0])
    else:
        ni = len(D[0])

    # Number of outputs
    if len(C) == 0:
        no = len(D)
    else:
        no = len(C)

    ####################
    # Open output file #
    ####################
    if len(args) == 4:
        filename = 'STATSP.ssp'
    else:
        filename = args[4]

    try:
        fid = open(filename, 'w')
    except IOError as e:
        raise AMESimError('ss2ame', 'unable to write in ' + filename) from e

    ########################
    # Write formatted data #
    ########################

    # Indicate it is a space state submodel
    fid.write('STATSP "Continuous state space"\n')

    # Number of states, outputs, inputs
    fid.write('%i number of states\n' % ns)
    fid.write('%i number of outputs\n' % no)
    fid.write('%i number of inputs\n' % ni)

    # A matrix
    for i in range(ns):
        for j in range(ns):
            fid.write('%.17e A(%i,%i)\n' % (A[i][j], i + 1, j + 1))

    # B matrix
    for i in range(ns):
        for j in range(ni):
            fid.write('%.17e B(%i,%i)\n' % (B[i][j], i + 1, j + 1))

    # C matrix
    for i in range(no):
        for j in range(ns):
            fid.write('%.17e C(%i,%i)\n' % (C[i][j], i + 1, j + 1))

    # D matrix
    for i in range(no):
        for j in range(ni):
            fid.write('%.17e D(%i,%i)\n' % (D[i][j], i + 1, j + 1))

    # State variable values
    if len(xvals) != 0:
        if isinstance(xvals[0], list):
            for j in range(ns):
                fid.write('%.17e x(%i)\n' % (xvals[j][0], j + 1))
        else:
            for j in range(ns):
                fid.write('%.17e x(%i)\n' % (xvals[j], j + 1))

    fid.close()
    return


def ame2data(*args):
    """
    ame2data Load AMESim format plot file.

    Load AMESim data file produced using the "Save as" facility on the
    pulldown menu of a plot and chosing the Format "Values".

    xy = ame2data('filename') returns the list xy which is the size the
    number of points by the number of quantities. The first list of xy
    contains the x-axis values and the following contains the y-axis
    quantities.
    If the pylab module is found, it produces the plot of the loaded data.

    When invoked with no 'filename' argument, ame2data asks for 'filename'

    See also ameloadt, data2ame, transposelist

    Copyright (C) 2019 by Siemens Industry Software NV
    """

    ###################################
    # Check number of input arguments #
    ###################################
    if len(args) > 1:
        raise AMESimError('ame2data', 'ame2data requires maximum one argument')

    ####################
    # Ask for filename #
    ####################
    if len(args) == 0:
        filename = openmyfile('Name of the AMESim format plot file: ', 'AMESim plot files', '*.dat*')
    else:
        filename = args[0]

    #############
    # Open file #
    #############
    try:
        fid = open(filename, 'r')
    except IOError as e:
        raise AMESimError('ame2data', 'unable to open ' + filename) from e

    ##########################
    # Read formatted strings #
    ##########################

    # First, check if it is an old style file or if it has a # on the first line
    theline = fid.readline()
    if theline[0] == '#':
        theline = fid.readline().strip()
        if theline.find('row') != -1:
            m = int(theline.split()[1])
        elif theline.find('columns') != -1:
            n = int(theline.split()[1])
        else:
            fid.close()
            raise AMESimError('ame2data', 'Incorrect format in PLOT file ' + filename + '. See AMESim documentation.')
        theline = fid.readline().strip()
        if theline.find('row') != -1:
            m = int(theline.split()[1])
        elif theline.find('columns') != -1:
            n = int(theline.split()[1])
        else:
            fid.close()
            raise AMESimError('ame2data', 'Incorrect format in PLOT file ' + filename + '. See AMESim documentation.')

        n = n - 1
    else:
        theline = theline.strip()
        if theline == theline.split()[0]:  # Are number of y-axes quantites on the same line as Number of data points ?
            n = int(theline)
            theline = fid.readline().strip()
            if theline != theline.split()[0]:
                raise AMESimError('ame2data', 'Incorrect format in file ' + filename + '. See AMESim documentation.')
            m = int(theline)
        else:
            try:
                n = int(theline.split()[0])  # Number of y-axes quantities
                m = int(theline.split()[1])  # Number of data points
            except Exception:
                raise AMESimError('ame2data', 'Incorrect format in file ' + filename + '. See AMESim documentation.')
    xy = []
    while 1:
        theline = fid.readline()
        if not theline:
            break
        theline = theline.strip()
        listline = theline.split()
        lenlist = len(listline)
        if lenlist != n + 1:
            fid.close()
            raise AMESimError('ame2data', 'incorrect format or bad number of data in file ' + filename)

        for i in range(lenlist):
            listline[i] = float(listline[i])
        xy.append(listline)

    fid.close()

    #########################
    # Plot data if possible #
    #########################
    try:
        from pylab import plot, show
    except ImportError:
        _printError('Install the pylab module to plot results')
        return xy
    xytoplot = transposelist(xy)
    for i in range(1, n):
        xytoplot.insert(2 * i, xytoplot[0])
    plot(*xytoplot)
    show()
    return xy


def amegetfinalvalues(sys_name='', dataset=_DATASET_REF):
    """AMEGETFINALVALUES()

   Get values of all variables at the end of a simulation, even variables
   that are not saved.

   Synopsis :
   ==========

   [FinalValues, VarNames] = amegetfinalvalues(sys_name)

   Input :
   =======

   sys_name  : (optional) name of model without extension. If the name is
               missing, a dialog box let the user choose the file by himself.

   Output :
   ========

   FinalValues  : a list of double, containing the final values of all
                  variables in the system
   VarNames     : a list of all variables in the system, in the same order
                  as in FinalValues
   """
    #
    # 2010/07/07 PGr 0098698: Deal with input variables extracting variables from vl file.
    #
    import tkinter.filedialog

    unique_identifier_keyword = 'Data_Path'

    # If name is missing, ask it
    if sys_name == '':
        sys_name = tkinter.filedialog.askopenfilename(filetypes=[('AMEsim model file', '.ame')],
                                                      title='Open an AMESim model file')
        if len(sys_name) == 0:
            return [[], []]

    # Check filename
    sys_name = getSystemName(sys_name)

    # Check if files exist
    filename_result = sys_name + '_.results'
    if dataset != _DATASET_REF:
        try:
            dataset=int(dataset)
        except (ValueError, TypeError):
            raise AMESimError(getnamefromui, "invalid dataset")
        filename_result = f"{filename_result}.{dataset}"
    
    result_exist = os.path.exists(filename_result)
    if not result_exist:
        raise AMESimError("amegetfinalvalues", filename_result + ' is missing. Please, check the model.')

    # Read .vl file

    # vl_file_path = sys_name+'_.vl'
    _variablesList.setVLPath(sys_name, dataset)
    _variablesList.update()

    VarNames = []
    for var in _variablesList.getAllVariables():
        VarNames.append(var.getName_instance())

    # Add time variable at the beginning
    VarNames.insert(0, 'Time [s]')

    # Strip linefeed and unique identifier
    nvartotal = len(VarNames)
    for k in range(nvartotal):
        VarNames[k] = VarNames[k].rstrip('\n')
        ui_pos = VarNames[k].find(' ' + unique_identifier_keyword)
        if ui_pos != -1:
            VarNames[k] = VarNames[k][0:ui_pos]

    # Try to open the .result binary file
    try:
        fh = open(filename_result, 'rb')
    except IOError:
        _printError('Unable to open ' + filename_result + '. Please, check the model.')
        return [[], []]

    # Read number of samples, and number of (saved) variables
    int_size = struct.calcsize('i')
    read_str = fh.read(2 * int_size)
    (ntime, nvar) = struct.unpack('2i', read_str)

    # Process the case of saved variables
    if nvar < 0:
        allSaved = False
        nvar = abs(nvar)
        # Skip nvar saved variables indexes
        fh.read(nvar * int_size)
    else:
        allSaved = True

    # Add +1 for time variable
    nvar = nvar + 1

    # Skip values
    block_size_to_skip = ntime * nvar

    # All variable are saved
    if allSaved:
        block_size_to_skip = (ntime - 1) * nvar

    double_size = struct.calcsize('d')
    fh.read(block_size_to_skip * double_size)

    # Read final values
    array = np.fromfile(fh, np.dtype('d'), nvartotal * double_size)

    FinalValues = array.tolist()
    fh.close()
    # Duplicate results
    for input in _variablesList.getAllInputs():
        idx = input.getNum()
        FinalValues.append(FinalValues[idx])

    return [FinalValues, VarNames]


def amesetfinalvalues(sys_name=''):
    """ AMESETFINALVALUES()

   Behaves like the 'Set Final Values' command in 'Settings' menu of AMESim.

   Synopsis :
   ==========

   retval = amesetfinalvalues(sys_name)

   Input :
   =======

   sys_name  : (optional) the name of a previously opened AMESim model
               (with no extension, or ending with .ame).  If the name is
               missing, a dialog box let the user choose the file by himself.

   Output :
   ========

   retval    : True if final values are correctly set, False otherwise.
   """
    import tkinter.filedialog

    unique_identifier_keyword = 'Data_Path'

    if sys_name == '':
        # If name is missing, ask it
        sys_name = tkinter.filedialog.askopenfilename(filetypes=[('AMEsim model file', '.ame')],
                                                      title='Open an AMESim model file')
        if len(sys_name) == 0:
            return False

    # Check filename
    sys_name = getSystemName(sys_name)

    # Check if files exist
    files_exist = True
    msg = ''
    for file_ext in ['_.results', '_.var', '_.param', '_.state']:
        if not os.path.exists(sys_name + file_ext):
            msg = msg + sys_name + file_ext + ' '
            files_exist = False
    if not files_exist:
        _printError('Some files are missing : ' + msg + '\nPlease, check the model.')
        return False

    # Try to open the .state file
    try:
        fh = open(sys_name + '_.state', 'rb')  # open in binary mode, decode later to support legacy encoding
    except OSError:
        _printError('Unable to open ' + sys_name + '_.state')
        return False

    # Read state variables
    StateName = [_decodeBytes(l) for l in fh.readlines()]
    fh.close()

    # Strip linefeed and unique identifier
    for k in range(len(StateName)):
        StateName[k] = StateName[k].rstrip('\n')
        ui_pos = StateName[k].find(' ' + unique_identifier_keyword)
        if ui_pos != -1:
            StateName[k] = StateName[k][0:ui_pos]

    # Get final values
    [FinalValues, VarNames] = amegetfinalvalues(sys_name)

    # Look for state variables final value
    for sn in StateName:
        try:
            l = VarNames.index(sn)
        except ValueError:
            continue
        StateValue = FinalValues[l]
        [ParName, ParVal] = _amegetp(True, sys_name, sn)
        if len(ParName) == 0:
            _printError('There is not any parameter found for state ' + sn)
            return False
        # Merge final values into .data file
        ameputp(sys_name, sn, StateValue)

    # Final values are correctly set
    return True

def amersmread(rsm_file: str) -> dict:
    """ Load RSM text file and compute RSM dictionary

    :param str rsm_file: RSM full path file
    :return: RSM parameters
    :rtype: dict
    """
    rsm_data = {}
    res = ""

    try:
        with open(rsm_file, 'rb') as fd:
            file_data = [_decodeBytes(l) for l in fd.readlines()]
        assert len(file_data) > 1, "RSM file corrupted"
        assert file_data[0].strip() == "# Table format: RSM", "RSM file corrupted"

        nb_input = 0
        nb_output = 0
        name_input = []
        name_output = []
        x0 = []
        poly = []
        idx_io = 0
        nb_monomial = 0
        set_monomial = set()
        c_fsm = 'global'
        state_fsm = {'global': 0, 'title': 0, 'units': 0, 'minmax': 0, 'output': 0}

        next_state = 0
        next_fsm = c_fsm

        tab_transition = {
            'global': {
                0: [(r"#\s+Table format:\s+RSM$", 1, 'global')],
                1: [(r"#\s+sizes$", 2, 'global')],
                2: [(r"#\s+(?P<NB_INPUT>\d+)\s+inputs$", 3, 'global')],
                3: [(r"^#\s+(?P<NB_OUTPUT>\d+)\s+outputs$", 4, 'global')],
                4: [(r"#\s+titles$", 0, 'titles'), (r"#\s+units$", 0, 'units'),
                    (r"#\s+minmax$", 0, 'minmax'),
                    (r"^#\s+output(?P<NUM_OUTPUT>\d+)$", 5, 'global')],
                5: [(r"#\s+offset$", 6, 'global')],
                6: [(r".+", 7, 'global')],
                7: [(r"#\s+RSM$", 8, 'global')],
                8: [(r".+", 9, 'global')],
                9: [(r"^#\s+output(?P<NUM_OUTPUT>\d+)$", 5, 'global'), (r".+", 9, 'global')],
            },
            'titles': {
                0: [(r"^#\s+input(?P<NUM_INPUT>\d+)_title\s+=\s+(?P<NAME_INPUT>.+)$", 0, 'titles'),
                    (r"^#\s+output(?P<NUM_OUTPUT>\d+)_title\s+=\s+(?P<NAME_OUTPUT>.+)$", 1, 'titles')],
                1: [(r"^#\s+output(?P<NUM_OUTPUT>\d+)_title\s+=\s+(?P<NAME_OUTPUT>.+)$", 1, 'titles'),
                    (r"#\s+units$", 0, 'units'),
                    (r"#\s+minmax$", 0, 'minmax'),
                    (r"^#\s+output(?P<NUM_OUTPUT>\d+)$", 5, 'global')]
            },
            'units': {
                0: [(r"^#\s+input(?P<NUM_INPUT>\d+)_unit\s+=\s+(?P<UNIT_INPUT>.+)$", 0, 'units'),
                    (r"^#\s+output(?P<NUM_OUTPUT>\d+)_unit\s+=\s+(?P<UNIT_OUTPUT>.+)$", 1, 'units')],
                1: [(r"^#\s+output(?P<NUM_OUTPUT>\d+)_unit\s+=\s+(?P<UNIT_OUTPUT>.+)$", 1, 'units'),
                    (r"#\s+minmax$", 0, 'minmax'),
                    (r"^#\s+output(?P<NUM_OUTPUT>\d+)$", 5, 'global')]
            },
            'minmax': {
                0: [(r".+", 1, 'minmax')],
                1: [(r".+", 2, 'minmax')],
                2: [(r"^#\s+output(?P<NUM_OUTPUT>\d+)$", 5, 'global')]
            }
        }

        id_output = 0
        for f_data in file_data:
            f_data = f_data.strip()

            # Empty line
            if f_data == "":
                continue

            # Test transition to go to next step
            match = None
            found_transition = False
            for (a_re, a_step, a_fsm) in tab_transition[c_fsm][state_fsm[c_fsm]]:
                match = re.match(a_re, f_data)
                if match is not None:
                    found_transition = True
                    next_state = a_step
                    next_fsm = a_fsm
                    break

            # Do action of the transition
            if found_transition:
                if (next_state, next_fsm) == (3, 'global'):
                    nb_input = int(match.group('NB_INPUT'))
                    assert nb_input >= 0, "RSM file corrupted: (number of inputs)"
                    name_input = [f'in_{k}' for k in range(nb_input)]
                elif (next_state, next_fsm) == (4, 'global'):
                    nb_output = int(match.group('NB_OUTPUT'))
                    assert nb_output > 0, "RSM file corrupted: (number of outputs)"
                    poly = [[] for _ in range(nb_output)]
                    x0 = [[] for _ in range(nb_output)]
                    name_output = [f'out_{k}' for k in range(nb_output)]
                elif (next_state, next_fsm) == (0, 'titles'):
                    if c_fsm == 'global':
                        idx_io = 0
                    else:
                        id_input = int(match.group('NUM_INPUT'))
                        assert id_input == (idx_io + 1), "RSM file corrupted: (input's titles)"
                        name_input[idx_io] = match.group('NAME_INPUT')
                        idx_io += 1
                elif (next_state, next_fsm) == (1, 'titles'):
                    if state_fsm[c_fsm] == 0:
                        assert nb_input == idx_io, "RSM file corrupted: (input's titles)"
                        idx_io = 0
                    id_output = int(match.group('NUM_OUTPUT'))
                    assert id_output == (idx_io + 1), "RSM file corrupted: (output's titles)"
                    name_output[idx_io] = match.group('NAME_OUTPUT')
                    idx_io += 1
                elif (next_state, next_fsm) == (0, 'units'):
                    if c_fsm == 'global':
                        idx_io = 0
                    elif c_fsm == 'titles':
                        assert nb_output == idx_io, "RSM file corrupted: (output's titles)"
                        idx_io = 0
                    else:
                        id_input = int(match.group('NUM_INPUT'))
                        assert id_input == (idx_io + 1), "RSM file corrupted: (input's units)"
                        idx_io += 1
                elif (next_state, next_fsm) == (1, 'units'):
                    if state_fsm[c_fsm] == 0:
                        assert nb_input == idx_io, "RSM file corrupted: (input's units)"
                        idx_io = 0
                    id_output = int(match.group('NUM_OUTPUT'))
                    assert id_output == (idx_io + 1), "RSM file corrupted: (output's units)"
                    idx_io += 1
                elif (next_state, next_fsm) == (0, 'minmax'):
                    if c_fsm == 'titles':
                        assert nb_output == idx_io, "RSM file corrupted: (output's titles)"
                    elif c_fsm == 'units':
                        assert nb_output == idx_io, "RSM file corrupted: (output's units)"
                elif (next_state, next_fsm) == (1, 'minmax'):
                    pattern = r"([-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)"
                    min_xy = [k[0] for k in re.findall(pattern, f_data)]
                    assert len(min_xy) == (nb_input + nb_output), 'RSM file corrupted: section "minmax (min values)"'
                elif (next_state, next_fsm) == (2, 'minmax'):
                    pattern = r"([-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)"
                    max_xy = [k[0] for k in  re.findall(pattern, f_data)]
                    assert len(max_xy) == (nb_input + nb_output), 'RSM file corrupted: section "minmax (max values)"'
                elif (next_state, next_fsm) == (5, 'global'):
                    if c_fsm == 'titles':
                        assert nb_output == idx_io, "RSM file corrupted: (output's titles)"
                        idx_io = 0
                    elif c_fsm == 'units':
                        assert nb_output == idx_io, "RSM file corrupted: (output's units)"
                        idx_io = 0
                    elif c_fsm == 'minmax':
                        idx_io = 0
                    elif state_fsm[c_fsm] < 5:
                        idx_io = 0
                    else:
                        idx_io += 1
                    id_output = int(match.group('NUM_OUTPUT'))
                    nb_monomial = 0
                    set_monomial = set()
                    assert id_output == (idx_io + 1), 'RSM file corrupted: section "output"'
                elif (next_state, next_fsm) == (7, 'global'):
                    pattern = r"([-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)"
                    offset = [k[0] for k in  re.findall(pattern, f_data)]
                    assert len(offset) == nb_input, f'RSM file corrupted: section "offset" of output {id_output}'
                    x0[idx_io] = [float(k) for k in offset]
                elif (next_state, next_fsm) == (9, 'global'):
                    x = [k.strip() for k in f_data.split()]
                    assert len(x) == nb_input + 1, f'RSM file corrupted: section "RSM" of output {id_output}'
                    pattern = r"\d+"
                    kx = [k[0] for k in re.findall(pattern, ' '.join(x[:-1]))]
                    assert len(kx) == nb_input, f'RSM file corrupted: section "RSM" of output {id_output}'
                    pattern = r"([-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)"
                    v = [k[0] for k in re.findall(pattern, x[-1])]
                    assert len(v) == 1, f'RSM file corrupted: section "RSM" of output {id_output}'
                    assert tuple(kx) not in set_monomial, f'RSM file corrupted: section "RSM" of output {id_output},' \
                                                          f' duplicate monomial'
                    set_monomial.add(tuple(kx))
                    kx.append(v[0])
                    poly[idx_io].append(kx)
            else:
                assert False, "RSM file corrupted"

            # Update current state and fsm
            c_fsm = next_fsm
            state_fsm[c_fsm] = next_state

        rsm_data['kls'] = [np.array([float(v[-1]) for v in p], "f8") for p in poly]
        rsm_data['M'] = [np.array([[int(k) for k in v[:-1]] for v in p], "u4") for p in poly]
        rsm_data['inputs_name'] = name_input
        rsm_data['outputs_name'] = name_output
        rsm_data['X0'] = np.array(x0, "f8")

    except (OSError, ValueError) as _:
        res = f"Error reading {rsm_file}"
    except AssertionError as e:
        res = e.args[0]

    if bool(res):
        raise AMESimError('amersmread', res)

    return rsm_data

def amersmeval(rsm: dict=None, inputs: list=None):
    """
    Evaluate rsm at given input values.

    inputs must be of size (number of samples x number of inputs)
    output_values will be of size (number of samples x number of outputs)

    Example, if RSM has 3 inputs, evaluation in zero is
    outputs = amersmeval(rsm_model, [0, 0, 0]);
    """
    outputs = []

    # Unfold data
    try:
        M = rsm['M']
        kls = rsm['kls']
        X0 = rsm['X0']
        n_inputs = M[0].shape[1]
        n_outputs = len(M)
        assert(n_outputs > 0)
    except:
        raise Exception("Invalid or empty RSM.")

    if type(inputs) not in [list, np.array, np.ndarray]:
        raise Exception("Missing inputs.")

    # if type(inputs) is list:
    inputs = np.asarray(inputs)
    if inputs.ndim == 1:
        inputs = np.reshape(inputs, (1, len(inputs)))
    if inputs.shape[1] != n_inputs:
        raise Exception("Inputs should have %i columns." % n_inputs)
    n_samples = inputs.shape[0]

    # Evaluate all outputs
    outputs = np.zeros((n_samples, n_outputs))
    for i in range(n_outputs):
        klsi = kls[i]
        Mi = M[i]
        X0i = X0[i]

        # Shift inputs
        u = np.zeros((n_samples, n_outputs))
        for p in range(n_inputs):
            u[:, p] = inputs[:, p] - X0i[p]

        # Evaluate
        n_par = Mi.shape[0]
        A = np.zeros((n_samples, n_par))
        a1 = np.ones(n_samples)
        for k in range(n_par):
            ak = a1.copy()
            for j in range(Mi.shape[1]):
                if Mi[k, j] > 0:
                    ak *= np.power(u[:, j], Mi[k, j])
            A[:, k] = ak.copy()
        yi = A @ np.reshape(klsi, (len(klsi), 1))
        outputs[:, i] = yi.T

    if n_samples == 1:
        outputs = outputs[0]

    return outputs

def amersmreadrsm(filename, num_response):
    """amersmreadrsm reads a Response Surface Model generated from AMESim.

    amersmreadrsm is capable of loading:
      one of the matrices of quadratic form
      one of the vectors of coefficients of the polynomial

    The principle is the following :

      amersmreadrsm(rsm_file, response_number) returns the matrix or
      the vector of the response_number-th output in the rsm_file.

    See also amersmcreatevec

    Copyright (c) 2019 Siemens Industry Software NV
    """
    try:
        fid = open(filename, 'rb')  # open in binary mode, decode later to support legacy encoding
    except IOError as e:
        raise AMESimError('amersmreadrsm', 'unable to read ' + filename) from e

    rsmType = 1  # The response surface is written in quadratic form
    # by default (first order, mixed first order or second order)
    id_response = 0
    while True:
        # Read line-by-line until end of file
        line = _decodeBytes(fid.readline())
        if not line:
            break
        line = line.strip()
        # Parse and branch
        if line.find('Type of RSM:') != -1:
            tok = line.split(':')
            if len(tok) >= 3 and tok[1].find('order') != -1:
                rsmType = int(tok[2].strip())
        elif line.find('factor(s):') != -1:
            tok = line.split()
            if len(tok) >= 2:
                nbfactors = int(tok[0].strip())
        elif line.find('response variable(s):') != -1:
            tok = line.split()
            if len(tok) >= 2:
                nbresponses = int(tok[0].strip())
                if num_response > nbresponses:
                    _printError('Error: there are only ', nbresponses, ' response(s)')
                    fid.close()
                    return []
        elif line.find('START') != -1:
            # Read next data section
            id_response += 1
            if id_response != num_response:
                continue
            matrix_out = []
            if rsmType < 3:
                # Read a matrix (Quadratic form)
                for k in range(nbfactors + 1):
                    data_line = _decodeBytes(fid.readline())
                    data_line = data_line.replace(';', ' ')
                    data_line = data_line.strip()
                    elems = data_line.split()
                    for l in range(len(elems)):
                        elems[l] = float(elems[l])
                    matrix_out.append(elems)
            else:
                # Read a vector (Polynomial form)
                data_line = _decodeBytes(fid.readline())
                while data_line.find('END') == -1:
                    data_line = data_line.strip()
                    tok = data_line.split(';')
                    matrix_out.append(float(tok[0].strip()))
                    data_line = _decodeBytes(fid.readline())
            fid.close()
            return matrix_out

    _printError('unable to find response')
    fid.close()


def amersmcreatevec(input_vector, rsmOrder):
    """amersmcreatevec Create a Response Surface Model vector from values.

    amersmcreateVec creates the vector X from the values of the
    parameters. It sorts all the terms including cross terms. To
    get the same order as in the rsm file, the same algorithm as in
    the c++ code is used.
    Then the approach values is given by:
       transpose(X)*poly_coef.
    That is to say, if P is a vector that contains the values of
    each parameter, the approach response is given by :
      Transpose ( createVec(P, rsm_order) ) * readRsm(rsm_file, response_number)
    See also amersmreadrsm

    Copyright (c) 2019 Siemens Industry Software NV
    """
    debugging_mode = False
    # Initialize a pseudo-global list used
    # to accumulate factors during recursion
    output_vector = []

    def multinomial(x, i, n):
        """Calculates multinomial factors of order 0 to n. x is a vector of power values,
        and i is the current variable index."""
        # Terminate recursion if last variable is reached
        if i == len(x) - 1:
            sumall = 0
            for xr in x:
                sumall += xr
            if sumall == n:
                if debugging_mode:
                    _print(sumall, x)
                # Add a new element by forming the product
                # of each variable from input_vector to the power x
                factor = 1
                for k in range(len(x)):
                    factor *= input_vector[k] ** x[k]
                output_vector.append(factor)
        else:
            # Remaining value from previous variables
            sumprev = 0
            if i >= 0:
                for xr in x[0:i + 1]:
                    sumprev += xr
            # Loop in descending order around the power of current variable
            for k in range(n - sumprev, -1, -1):
                x[i + 1] = k
                multinomial(x, i + 1, n)  # recursive call

    # Initialize vector of power of variables in input_vector
    x = [0] * len(input_vector)
    # Generate order 0 terms, then order 1 terms, ..., up to rsmOrder
    for k in range(0, rsmOrder + 1):
        multinomial(x, -1, k)
    return output_vector


def amebode(*args):
    """amebode Bode frequency response for linearized AMESim systems

    amebode('system') extracts continuous state-space matrix (A,B,C,D)
    computed by AMESim, produces a Bode plot and returns matrices
    wout(in rad/s), mag and phase (in degrees).

    amebode without right arguments asks the user for the name of the system.

    If there is more than one control variable or more than one observer
    variable, this function ask for which one you want to use.

    amebode('system',w,uindex,yindex,jac_id,run_id) uses the user-
    supplied frequency vector w which must contain the frequencies, in
    radians/sec, at which the Bode response is to be evaluated. uindex and
    yindex are respectively the indexes of the control and observer variable
    selected in AMESim. jac_id is the id of the Jacobian. run_id is used to
    specify the batch run number.
    Note that jac_id starts from 0, while batch run_id starts from 1.

    See also ameloadj, bode, control system toolbox
    """

    _printError('Warning: "amebode" function is deprecated. '
                'Consider using "ameloadj" to get the state-space matrices then "scipy" and "ampyplot" Python modules'
                ' to compute and plot the magnitude and phase of transfer function.')

    [wout, mag, phase] = amebode_compute(*args)

    amebode_plot(wout, mag, phase)

    return [wout, mag, phase]


def amebode_compute(*args):
    """amebode_compute Compute Bode frequency response

    amebode_compute('system') extracts continuous state-space matrix (A,B,C,D)
    computed by AMESim and returns matrices wout(in rad/s), mag and phase
    (in degrees). These matrices can be used to create a bode plot using the
    amebode_plot function.

    amebode_compute without right arguments asks user for the name of the system.

    If there is more than one control variable or more than one observer
    variable, this function asks for which one you want to use.

    amebode_compute('system',w,uindex,yindex,jac_id,run_id) uses the user-
    supplied frequency vector w which must contain the frequencies, in
    radians/sec, at which the Bode response is to be evaluated. uindex and
    yindex are respectively the indexes of the control and observer variable
    selected in AMESim. jac_id is the id of the Jacobian. run_id is used to
    specify the batch run number.
    Note that jac_id starts from 0, while batch run_id starts from 1.

    See also ameloadj, bode, control system toolbox
    """

    _printError('Warning: "amebode_compute" function is deprecated.'
                'Consider using "ameloadj" to get the state-space matrices then "scipy" Python module to compute the'
                ' magnitude and phase of transfer function.')

    ###################################
    # Check number of input arguments #
    ###################################

    if len(args) > 6:
        raise AMESimError('amebode', 'too many input arguments')

    ######################
    # Load jacobian file #
    ######################
    if len(args) == 0:
        [A, B, C, D, x, u, y, t, S] = ameloadj()
    else:
        sname = args[0]
        if len(args) < 5:
            [A, B, C, D, x, u, y, t, S] = ameloadj(sname)
        elif len(args) == 5:
            [A, B, C, D, x, u, y, t, S] = ameloadj(sname, args[4])
        elif len(args) == 6:
            [A, B, C, D, x, u, y, t, S] = ameloadj(sname, args[4], args[5])

    ################
    # Select input #
    ################
    ncv = len(u)
    if ncv == 0:
        raise AMESimError('amebode', 'there is no control variable for this system')
    elif ncv == 1:
        uindex = 1
    else:
        if len(args) < 3:  # uindex is not given
            _print('List of inputs:')
            for iter_var in range(ncv):
                _print(' ' + u[iter_var] + '....:' + str(iter_var + 1))
            uindex = int(input('Your choice: ').strip())
        else:
            uindex = args[2]

    if uindex > ncv or uindex < 1:
        raise AMESimError('amebode', 'wrong control variable index')
    else:
        uname = u[uindex - 1]

    #################
    # Select output #
    #################
    nov = len(y)
    if nov == 0:
        raise AMESimError('amebode', 'there is no observer variable for this system')
    elif nov == 1:
        yindex = 1
    else:
        if len(args) < 4:  # yindex is not given
            _print('List of outputs :')
            for iter_var in range(nov):
                _print(' ' + y[iter_var] + '....' + str(iter_var + 1))
            yindex = int(input('Your choice: ').strip())
        else:
            yindex = args[3]

    if yindex > nov or yindex < 1:
        raise AMESimError('amebode', 'wrong observer variable index')
    else:
        yname = y[yindex - 1]

    ####################################
    # Evaluate Bode frequency response #
    ####################################
    indexnil = len(B) - 1  # Index of nilpotency

    try:
        import scipy
    except ImportError:
        _printError('Install scipy to compute the Bode frequency response')
        _printError('See http://www.scipy.org')
        return [[], [], []]

    # Get frequency range
    if len(args) > 1:
        wrange = scipy.array(args[1])
    else:
        wrange = 2 * scipy.pi * np.arange(0, 100)  # by default 0 Hz ... 100 Hz

    # Explicit system
    sys_a = scipy.matrix(A)
    sys_b = scipy.zeros((len(B[0]), 1))
    for k in range(len(B[0])):
        sys_b[k, 0] = B[0][k][uindex - 1]
    sys_c = scipy.matrix(C[yindex - 1])
    sys_d = D[0][yindex - 1][uindex - 1]
    wout, mag, phase = compute_bode(sys_a, sys_b, sys_c, sys_d, wrange)

    # Implicit case
    if indexnil > 0:
        z = scipy.multiply(mag, scipy.exp(1j * phase * scipy.pi / 180.0))
        for iter_var in range(1, indexnil + 1):
            sys_b = scipy.zeros((len(B[iter_var]), 1))
            for k in range(len(B[iter_var])):
                sys_b[k, 0] = B[iter_var][k][uindex - 1]
            sys_d = D[iter_var][yindex - 1][uindex - 1]
            wout, mag, phase = compute_bode(sys_a, sys_b, sys_c, sys_d, wrange)
            z1 = scipy.multiply(mag, scipy.exp(1j * phase * scipy.pi / 180.0))
            z += scipy.multiply(scipy.power(1j * wout, iter_var), z1)
        mag = abs(z)
        phase = scipy.arctan2(z.imag, z.real) * 180.0 / scipy.pi

    return [wout, mag, phase]


def amebode_plot(wout, mag, phase):
    """amebode_plot Create a Bode plot

    To create a bode plot, first compute the wout, mag and phase arguments
    using the amebode_compute function, then call this function.

    Eg:      [wout, mag, phase] = amebode_compute('system')
             amebode_plot(wout, mag, phase)
    """

    _printError('Warning: "amebode_plot" function is deprecated. '
                'Consider using "ampyplot" Python modules to plot the magnitude and phase of transfer function.')

    ##################
    # Draw bode plot #
    ##################
    import scipy
    freq_range = wout / (2 * scipy.pi)
    mag_dB = 20 * scipy.log10(mag)

    # By default we use amepyplot, but because PySide and TkInter apps are not compatible
    # we revert to using pylab if a TkInter app is detected
    if isTkInterAppPresent():
        _printError("Warning: TkInter applications in Amesim scripts are deprecated. Please use PySide instead.")
        try:
            import pylab
        except ImportError:
            raise AMESimError("amebode_plot", "Install the pylab module to plot results.")

        pylab.subplot(211)
        x, y = amesim_utils.positive_part(freq_range, mag_dB)
        pylab.semilogx(x, y)
        pylab.grid(True)
        pylab.title('Amplitude of frequency response (dB)')
        pylab.subplot(212)
        x, y = amesim_utils.positive_part(freq_range, phase)
        pylab.semilogx(x, y)
        pylab.grid(True)
        pylab.title('Phase of frequency response (deg)')
        pylab.xlabel('Frequency (Hz)')
        if not pylab.isinteractive():
            pylab.show()
        return

    try:
        import amepyplot
    except ImportError:
        raise AMESimError("amebode_plot", "Cannot import Amesim plot module. Please check your Amesim environment.")

    from PySide2 import QtWidgets

    # checks if QApplication already exists
    if QtWidgets.QApplication.instance() is None:  # create QApplication if it doesnt exist
        QtWidgets.QApplication([])

    plot = amepyplot.PlotWidget()
    plot.setRowCount(2)
    x, y = amesim_utils.positive_part(freq_range, mag_dB)
    x_item = amepyplot.Item(x, 'Frequency', 'Hz')
    y_item = amepyplot.Item(y, 'Gain', 'dB')
    ampl_curve = amepyplot.Curve2D(x_item, y_item, title='Amplitude of frequency response')
    ampl_graph = plot.getGraph(0, 0)
    ampl_graph.addCurve(ampl_curve)
    ampl_graph.xAxis().setLogScale(True)

    x, y = amesim_utils.positive_part(freq_range, phase)
    x_item = amepyplot.Item(x, 'Frequency', 'Hz')
    y_item = amepyplot.Item(y, 'Phase', 'deg')
    phase_curve = amepyplot.Curve2D(x_item, y_item, title='Phase of frequency response')
    phase_graph = plot.getGraph(1, 0)
    phase_graph.addCurve(phase_curve)
    phase_graph.xAxis().setLogScale(True)

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle('Bode Plot')
    dialog.resize(500, 400)
    layout = QtWidgets.QHBoxLayout(dialog)
    layout.addWidget(plot)
    dialog.show()
    dialog.exec_()


def compute_bode(a, b, c, d, wrange):
    """Computes Bode frequency response of a SISO LTI system defined
    by system matrix a and control vector b,
    oberver vector c, direct transfer coefficient d,
    over an angular frequency range wrange (in rad/s)
    and return modulus and argument of transfer function.

    [wout, mag, phase] = compute_bode(num, den, b, c, d, wrange)

    a : a matrix
    b : a column (scipy) vector
    c : a row (scipy) vector
    d : a scalar
    wrange : a (scipy) vector of angular frequencies (in rad/s)
    wout : a list of angular frequencies (in rad/s)
    mag : a list of modulus of transfer function
    phase : a list of phase angle (in degrees) of transfer function
    """
    import scipy.signal
    system = scipy.signal.lti(a, b, c, d)
    wout, y = scipy.signal.freqresp(system, [w for w in wrange if w])  # eliminate w = 0 values
    mag = abs(y)
    unwraped_phase = scipy.unwrap(scipy.arctan2(y.imag, y.real)) * 180.0 / scipy.pi

    # Return angular frequency, amplitude and unwrapped phase in degrees
    return scipy.matrix(wout), scipy.matrix(mag), scipy.matrix(unwraped_phase)


def amegetparamuifromname(sys_name, submodel='', instance='', name=''):
    """AMEGETPARAMUIFROMNAME
   Retrieves every parameter of a model matching a search criterion
   defined by submodel, instance, name.

   Synopsis:
   =========

   uids = amegetparamuifromname(sys_name, submodel, instance, name)

   Inputs:
   =======

   sys_name  : the name of a previously opened AMESim model
               (with no extension, or ending with .ame)
   submodel  : (optional) the name of a submodel or a complete search string
               including submodel name, instance number and parameter name
   instance  : (optional) instance number
   name      : (optional) parameter name

   Outputs:
   ========

   uids      : a list of unique identifier for matching parameters.

   Examples:
   =========

   uids = amegetparamuifromname('GasInjection', 'HL04')
      --> all parameters of all HL04 instance

   uids = amegetparamuifromname('GasInjection', 'HL04', 3)
      --> all parameters of HL04 instance 3

   uids = amegetparamuifromname('GasInjection', 'HL04', 3, 'relative roughness [null]')
      --> one parameter of HL04 instance 3

   uids = amegetparamuifromname('GasInjection', 'HL06', 3, 'pressure*')
      --> all parameters of HL06 instance 3 beginning with pressure

   uids = amegetparamuifromname('GasInjection')
      --> all parameters of all submodels of GasInjection.ame
   """

    # Check filename
    sys_name = getSystemName(sys_name)

    # Smartly concatenate submodel, instance, name
    search_str = submodel
    if instance:
        search_str = search_str + ' instance ' + str(instance)
    if name:
        search_str = search_str + ' ' + name

    # Call to work function
    return getuifromname(sys_name + '_.param', search_str)


def amegetparamnamefromui(sys_name, uid):
    """AMEGETPARAMNAMEFROMUI
   Retrieves the parameter name of a model given its unique identifier

   Synopsis:
   =========

   parname = amegetparamnamefromui(sys_name, uid)


   Inputs:
   =======

   sys_name  : the name of a previously opened AMESim model
               (with no extension, or ending with .ame)
   uid       : an unique identifier search criterion of the form
               uiname@pathcomponent1[.pathcomponent2[.pathcomponent3.[ ...]]]
               uiname is a unique identifier name, or a star (*),
               which matches every name for this data path.
               The last component of the data path may be a star (*),
               which matches every component beyond this level

   Outputs:
   ========

   parname   : a list of parameters name which unique identifier match
               the search critetion

   Examples:
   =========

   parname = amegetparamnamefromui('GasInjection', 'rp13@h2port_5')

   parname = amegetparamnamefromui('GasInjection', '*@h2port_5')

   parname = amegetparamnamefromui('GasInjection', 'offset@gasoline_injector*')
   """
    # Check filename
    sys_name = getSystemName(sys_name)

    # Call to work function
    return getnamefromui(sys_name + '_.param', uid)


def amegetvaruifromname(sys_name, submodel='', instance='', name='', dataset=_DATASET_REF):
    """AMEGETVARUIFROMNAME
   Retrieves every variable of a model matching a search criterion
   defined by submodel, instance, name.

   Synopsis:
   =========

   uids = amegetvaruifromname(sys_name, submodel, instance, name)

   Inputs:
   =======

   sys_name  : the name of a previously opened AMESim model
               (with no extension, or ending with .ame)
   submodel  : (optional) the name of a submodel or a complete search string
               including submodel name, instance number and variable name
   instance  : (optional) instance number
   name      : (optional) variable name

   Outputs:
   ========

   uids      : a list of unique identifier for matching variables.

   Examples:
   =========

   uids = amegetvaruifromname('GasInjection', 'HL04')
      --> all variables of all HL04 instance

   uids = amegetvaruifromname('GasInjection', 'HL04', 3)
      --> all variables of HL04 instance 3

   uids = amegetvaruifromname('GasInjection', 'HL04', 3, 'Reynolds number')
      --> one variables of HL04 instance 3

   uids = amegetvaruifromname('GasInjection', 'HL06', 3, 'pressure*')
      --> all variables of HL06 instance 3 beginning with pressure

   uids = amegetvaruifromname('GasInjection')
      --> all variables of all submodels of GasInjection.ame
   """
    #
    # 2010/07/07 PGr 0098698: Deal with input variables extracting variables from vl file.
    #

    # Check filename
    sys_name = getSystemName(sys_name)

    # Smartly concatenate submodel, instance, name if not in full string mode
    search_str = submodel or '*'

    full_string_search = submodel and ' ' in submodel and not name and not instance
    if not full_string_search:
        if instance:
            search_str += "_{}".format(instance)

        if name:
            search_str += " {}".format(name)
        elif not search_str.endswith('*'):
            search_str += '*'

    # Call to work function
    return getuifromname(sys_name + '_.vl', search_str, dataset)


def amegetvarnamefromui(sys_name, uid, dataset=_DATASET_REF):
    """AMEGETVARNAMEFROMUI
   Retrieves the variable name of a model given its unique identifier

   Synopsis:
   =========

   varname = amegetvarnamefromui(sys_name, uid)


   Inputs:
   =======

   sys_name  : the name of a previously opened AMESim model
               (with no extension, or ending with .ame)
   uid       : an unique identifier search criterion of the form
               uiname@pathcomponent1[.pathcomponent2[.pathcomponent3.[ ...]]]
               uiname is a unique identifier name, or a star (*),
               which matches every name for this data path.
               The last component of the data path may be a star (*),
               which matches every component beyond this level

   Outputs:
   ========

   varname   : a list of variables name which unique identifier match
               the search critetion

   Examples:
   =========

   varname = amegetvarnamefromui('GasInjection', 'p1@h2port_5')

   varname = amegetvarnamefromui('GasInjection', '*@h2port_5')

   varname = amegetvarnamefromui('GasInjection', 'qsig@gasoline_injector*')
   """
    #
    # 2010/07/07 PGr 0098698: Deal with input variables extracting variables from vl file.
    #
    # Check filename

    sys_name = getSystemName(sys_name)

    # Call work function and replace 'instance' by an undescore (_)
    # to be consistent with variable name list returned by ameloadt()
    return [v.replace(' instance ', '_', 1).strip() for v in getnamefromui(sys_name + '_.vl', uid, dataset)]


def getuifromname(filename, search_str, dataset=_DATASET_REF):
    """Retrieves one or many parameter or variable matching a search string
   """
    import os.path

    # Basic check on filename (*_.param or *_.param.* or *_.var or *_.var* or *_.vl or *_.vl.*)
    if ((filename.find('_.param') < 0) and
            (filename.find('_.var') < 0) and
            (filename.find('_.vl') < 0)):
        _printError('Filename does not end with .param or .var or .vl')
        return []

    ui_lst = []

    if search_str == 'time [s]':
        ui_lst.append('ame_simulation_time')
        return ui_lst

    if filename.find('_.param') >= 0 or filename.find('_.var') >= 0:
        if dataset != "ref":
            try:
                dataset=int(dataset)
            except (ValueError, TypeError):
                raise AMESimError("getnamefromui", "invalid dataset")
            filename = f"{filename}.{dataset}"
            
        # Check existance of the file
        if not os.path.exists(filename):
            raise AMESimError("getnamefromui", filename + ' does not not exist')

        # Preprocess instance number
        if re.compile(r'^[^\s-]+-\d+').search(search_str):
            search_str = search_str.replace('-', ' instance ', 1)

        # Preprocess star at end of search string
        if search_str and search_str[-1] == '*':
            search_str = search_str[0:-1]

        # Open file
        try:
            fobj = open(filename, 'rb')  # open in binary mode, decode later to support legacy encoding
        except OSError:
            _printError('Unable to open', filename)
            return []

        # Scan file line-by-line
        for curline in fobj:
            curline = _decodeBytes(curline)
            # Strip end of line
            cline = curline.rstrip()
            if cline == 'HIDDEN' or cline.startswith('_DUMMY') or amesim_utils.is_linked_variable(cline):
                continue
            # Parse line
            cline = re.sub(r' Is_Delta=[01]', '', cline)
            cline = re.sub(r' Param_Id=\d+', '', cline)
            cline = re.sub(r' Recompile_Flag=[01]', '', cline)
            cline = re.sub(amesim_utils.linked_variable_path_regex, '', cline)
            cline = re.sub(amesim_utils.is_linked_variable_regex, '', cline)
            name, data_path = cline[:cline.find(' Data_Path=')], cline[cline.find(' Data_Path=') + len(' Data_Path='):]
            # Apply search criterion
            if (search_str and name.find(search_str) > -1) or not search_str:
                ui_lst.append(data_path)

        # Terminate
        fobj.close()
    else:
        # Use ILVariablesList object to get variable infos
        _variablesList.setVLPath(filename, dataset)
        _variablesList.update()
        matching_variables = _variablesList.getVariableFromName(search_str)
        for variable in matching_variables:
            if variable.getDataPath():
                ui_lst.append(variable.getDataPath())

    return ui_lst


def getnamefromui(filename, uid, dataset=_DATASET_REF):
    """Retrieves one or many parameters or variables
   which unique identifiers are matching a search criterion
   """
    #
    # 2010/07/07 PGr 0098698: Deal with input variables extracting variables from vl file.
    #
    # Basic check on filename (*_.param or *_.param.* or *_.var or *_.var* or *_.vl or *_.vl.*)
    if ((filename.find('_.param') < 0) and
            (filename.find('_.var') < 0) and
            (filename.find('_.vl') < 0)):
        _printError('Filename does not end with .param or .var or .vl')
        return []

    name_lst = []
    if uid == 'ame_simulation_time':
        name_lst.append('time [s]')
        return name_lst

    # Check uid
    if uid.find('@') == -1:
        _printError('Search criterion must contain an at-sign (\'@\')')
        return []

    if filename.find('_.param') >= 0 or filename.find('_.var') >= 0:
        if dataset != _DATASET_REF:
            try:
                dataset=int(dataset)
            except (ValueError, TypeError):
                raise AMESimError("getnamefromui", "invalid dataset")
            filename = f"{filename}.{dataset}"
            
        if not os.path.exists(filename):
            raise AMESimError("getnamefromui", filename + ' does not not exist')
        # Strip arobace at beginning and end of line
        # and set search criterion
        if uid[0] == '*' and uid[-1] == '*':
            uid = uid[1:-1]
            search_fun = lambda s: s.find(uid) != -1
        elif uid[0] == '*':
            uid = uid[1:]
            search_fun = lambda s: s.endswith(uid)
        elif uid[-1] == '*':
            uid = uid[:-1]
            search_fun = lambda s: s.startswith(uid)
        else:
            search_fun = lambda s: s == uid

        # Open file
        try:
            fobj = open(filename, 'rb')  # open in binary mode, decode later to support legacy encoding
        except IOError:
            _printError('Unable to open', filename)
            return []

        # Scan file line-by-line
        for cline in fobj:
            cline = _decodeBytes(cline)
            # Strip end of line
            cline = cline.rstrip()
            if cline == 'HIDDEN' or cline.startswith('_DUMMY') or amesim_utils.is_linked_variable(cline):
                continue
            # Parse line
            cline = re.sub(r' Is_Delta=[01]', '', cline)
            cline = re.sub(r' Param_Id=\d+', '', cline)
            cline = re.sub(r' Recompile_Flag=[01]', '', cline)
            cline = re.sub(amesim_utils.linked_variable_path_regex, '', cline)
            cline = re.sub(amesim_utils.is_linked_variable_regex, '', cline)

            name, data_path = cline[:cline.find(' Data_Path=')], cline[cline.find(' Data_Path=') + len(' Data_Path='):]
            # Apply search criterion
            if search_fun(data_path):
                name_lst.append(name)

        fobj.close()

    else:
        # Use ILVariablesList object to get variable infos
        _variablesList.setVLPath(filename, data_set=dataset)
        _variablesList.update()
        matching_variables = _variablesList.getVariableFromDataPath(uid)
        for variable in matching_variables:
            name_lst.append(variable.getName())

    # Terminate
    return name_lst


def transposelist(L):
    L2 = []
    if not isinstance(L, list):
        raise AMESimError('transposelist', 'transposelist requires a list')
    if not isinstance(L[0], list):
        for e in L:
            L2.append([e])
    else:
        for i in range(len(L[0])):
            L2.append(range(len(L)))
            for j in range(len(L)):
                L2[i][j] = L[j][i]

    return L2


def abcdchk(a, b, c, d):
    ma = len(a)
    na = len(a[0])

    mb = len(b)
    nb = len(b[0])

    mc = len(c)
    nc = len(c[0])

    md = len(d)
    nd = len(d[0])

    if ma != na:
        raise AMESimError('abcdchk', 'the matrix A must be square')
    elif ma != mb:
        raise AMESimError('abcdchk', 'the A and B matrices must have the same number of rows')
    elif na != nc:
        raise AMESimError('abcdchk', 'the A and C matrices must have the same number of columns')
    elif md != mc:
        raise AMESimError('abcdchk', 'the C and D matrices must have the same number of rows')
    elif nd != nb:
        raise AMESimError('abcdchk', 'the B and D matrices must have the same number of columns')
    return


def openmyfile(*args):
    if len(args) == 3:
        messagetodisplay = args[0]
        filestype = args[1]
        extensionfile = args[2]
    else:
        messagetodisplay = 'Name of the system: '
        filestype = 'AMESim files'
        extensionfile = '*.ame'
    try:
        import tkinter, tkinter.filedialog
        try:
            root = tkinter.Tk()
            filetoopen = tkinter.filedialog.Open(root, filetypes=[(filestype, extensionfile), ('All files', '*')])
            sname = filetoopen.show()
            root.quit()
        except:
            sname = input(messagetodisplay)
    except ImportError:
        sname = input(messagetodisplay)

    return sname.strip()


def matfix(x):
    from math import floor, ceil
    if x < 0:
        return ceil(x)
    else:
        return floor(x)


def ameisvariableui(variable_identifier):
    """ameisvariableui tells if the variable_identifier argument is a variable uid
      (ex: flow1@node_2)"""
    if variable_identifier is None:
        return None
    return re.compile(r'^[a-zA-Z0-9]+\w*@[\w.]+').search(variable_identifier) is not None


def ameisvariablename_underscore(variable_identifier):
    """ameisvariablename_underscore tells if the variable_identifier argument is a variable name identifier
      like 'H3NODE1_1 flow rate at port 1 [L/s]'"""
    if variable_identifier is None:
        return None
    name_undescore_pattern = '^\\w+_\\d+ '
    return re.compile(name_undescore_pattern).match(variable_identifier) is not None


def ameisvariablename_instance(variable_identifier):
    """ameisvariablename_instance tells if the variable_identifier argument is a variable name identifier
      like 'H3NODE1 instance 1 flow rate at port 1 [L/s]'"""
    if variable_identifier is None:
        return None
    name_instance_pattern = '^\\w+ instance \\d+ '
    return re.compile(name_instance_pattern).match(variable_identifier) is not None


def ameisvariablename_minus(variable_identifier):
    """ameisvariablename_minus tells if the variable_identifier argument is a variable name identifier
      like 'H3NODE1-1 flow rate at port 1 [L/s]'"""
    if variable_identifier is None:
        return None
    name_minus_pattern = '^\\w+-\\d+ '
    return re.compile(name_minus_pattern).search(variable_identifier) is not None


def ameisvariablename(variable_identifier):
    """ameisvariablename tells if the variable_identifier argument is a variable name identifier
      (ex: H3NODE1_1 flow rate at port 1 [L/s] or H3NODE1-1 flow rate at port 1 [L/s] or
      H3NODE1 instance 1 flow rate at port 1 [L/s])"""
    return (ameisvariablename_underscore(variable_identifier) or
            ameisvariablename_instance(variable_identifier) or
            ameisvariablename_minus(variable_identifier))


def _read_integer_values(fid, count):
    """Private function used to read a list of integers from a file
    """
    values_list = []
    while len(values_list) < count:
        read_line = fid.readline()

        # We must consume empty lines
        while not read_line.strip():
            read_line = fid.readline()
            if not read_line:  # reached end of file
                break

        # If there is no more content, but somehow we expect to read more than
        # "count" number of values we abort the read
        if not read_line:
            break

        values_list += [int(x) for x in read_line.split()]

    return values_list


def _read_integer_counter(fid):
    """Private function used to read a counter
    """
    read_line = fid.readline()
    while not read_line.strip():
        read_line = fid.readline()
        if not read_line:
            break

    result = re.search(r'^(\d+)\D*$', read_line)
    return int(result.group(1)) if result else 0
