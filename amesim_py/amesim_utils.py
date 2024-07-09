# *****************************************************************************
#  This material contains trade secrets or otherwise confidential
#  information owned by Siemens Industry Software Inc. or its
#  affiliates (collectively, "Siemens"), or its licensors. Access to
#  and use of this information is strictly limited as set forth in the
#  Customer's applicable agreements with Siemens.
# 
#  Unpublished work. Copyright 2023 Siemens
# *****************************************************************************
import re
import time
import os


class AMESimError(Exception):
    def __init__(self, funcname, error):
        mess = "%s: %s" % (funcname, error)
        super(AMESimError, self).__init__(mess)
        self.funcname = funcname
        self.error = error


####################################################
# Constants related to Linked variables management #
####################################################
is_linked_variable_keyword = 'Is_Linked_Variable'
is_linked_variable_regex = ' ' + is_linked_variable_keyword + '=[01]'

linked_variable_path_keyword = 'Linked_Variable_Path'
linked_variable_path_regex = ' ' + linked_variable_path_keyword + r'=\S*@\S+'


def time_it(method):
    """Function decorator to benchmark function call"""
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        print('%r (%r, %r) %2.2f sec' % (method.__name__, args, kw, te-ts))
        return result

    return timed


def is_linked_variable(param_name):
    linked_variable_name_part_keyword = r' - Linked variable\s?\[.*\]'
    return re.search(linked_variable_name_part_keyword, param_name) is not None


def convertWildcardStringToRegexString(wildcard_string):
    # We escape the string because it may contain characters that have special meaning
    # inside a regex. By escaping the chars they will act as simple chars.
    regex_string = re.escape(wildcard_string)

    if regex_string:
        if regex_string[-1] != '*':
            regex_string = regex_string + r'(?:\s\[.*\]\s?)?'  # optional units suffix in square brackets (e.g. [Hz] )
            regex_string = regex_string + r'(?:\r|\n|$)'  # end of string
        if regex_string[0] != '*':
            regex_string = r'(?:^)' + regex_string

    # Because above we used re.escape(), we must replace all \* instead of all *
    return regex_string.replace(r'\*', r'[^\r\n]*')


def positive_part(x, y, whichvar='x'):
    """Utility function called by ameplot() and amebode()
      to prevent crashes in semilogx(), semilogy() and loglog()
      under Sun/Solaris 8 when these functions are called with
      non striclty positive argument (remark: This does not occur
      under Intel/Win32 and Intel/Linux).

      This function computes positive part of arguments.

      For whichvar == 'x', returns elements in x and y
      for which x is strictly positive

      For whichvar == 'y', returns elements in x and y
      for which y is strictly positive

      For whichvar == 'xy', returns elements in x and y
      for which x and y are strictly positive
   """
    from scipy import asarray, logical_and
    x = asarray(x)
    y = asarray(y)
    if whichvar == 'x':
        pos = x > 0
    elif whichvar == 'y':
        pos = y > 0
    elif whichvar == 'xy' or whichvar == 'yx':
        pos = logical_and(x > 0, y > 0)
    else:
        return x, y
    xp = x[pos]
    yp = y[pos]
    return xp, yp

#
# Extract from provided string the system name
#
# Examples:
# 'youpla'                      will return 'youpla'
# 'youpla.ame'                  will return 'youpla'
# 'youpla_.param'               will return 'youpla'
# 'youpla_.info/tutu'           will return 'youpla_.info/tutu'
# 'youpla_.info/tutu.ame'       will return 'youpla_.info/tutu'
# 'youpla_.info/tutu_.cir'      will return 'youpla_.info/tutu'
# 'youpla_.jac2.3'              will return 'youpla'
# 'C:/Data/youpla.ame'          will return 'C:/Data/youpla'
#
def getSystemName(name):
    # Remove extension and possibly "_"
    splitTup = os.path.splitext(name)
    systemName = splitTup[0]
    if systemName.endswith("_"):
        systemName = systemName[:-1]
    else:
        #Check if it is like systemName_.jac0.1 (batch files)
        splitTup = os.path.splitext(splitTup[0])
        systemName = splitTup[0]
        if systemName.endswith("_"):
            systemName = systemName[:-1]

    return systemName