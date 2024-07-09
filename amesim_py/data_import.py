# *****************************************************************************
#  This material contains trade secrets or otherwise confidential
#  information owned by Siemens Industry Software Inc. or its
#  affiliates (collectively, "Siemens"), or its licensors. Access to
#  and use of this information is strictly limited as set forth in the
#  Customer's applicable agreements with Siemens.
# 
#  Unpublished work. Copyright 2023 Siemens
# *****************************************************************************
import os
import ctypes
import data_import_utils as dimutils
from amesim_utils import AMESimError

__all__ = ["amereadtextfile", "amereadspreadsheetfile", "amegetsheetlist", "amegetsheetcount", "amewritetodatafile",
           "amewritetodatafile", "amewrite1dtabletofile", "amewritexytabletofile", "amewrite2dtabletofile",
           "amewritem1dtabletofile", "ameimportdata", "ameexportdata"]


if os.name == 'nt':
    scripting_api = ctypes.CDLL("scripting_api_interface")
elif os.name == 'posix':
    scripting_api = ctypes.CDLL("libscripting_api_interface.so")


def parse_args(*args):
    import argparse
    pass


class __FileData(ctypes.Structure):
    _fields_ = [('data', ctypes.POINTER(ctypes.c_double)),
                ('data_lengths', ctypes.POINTER(ctypes.c_int)),
                ('header', ctypes.POINTER(ctypes.c_char_p)),
                ('header_joined', ctypes.c_char_p),
                ('units', ctypes.POINTER(ctypes.c_char_p)),
                ('units_joined', ctypes.c_char_p),
                ]


class __ReadFileParams(ctypes.Structure):
    _fields_ = [('filename', ctypes.c_char_p),
                ('delimiter', ctypes.c_char_p),
                ('multiple_delimiters_as_one', ctypes.c_bool),
                ('column_width', ctypes.c_int),
                ('sheet_index', ctypes.c_int),
                ('sheet_name', ctypes.c_char_p),
                ('selection', ctypes.c_char_p),
                ('table_type', ctypes.c_char_p),
                ('header_row', ctypes.c_int),
                ('units_row', ctypes.c_int),
                ('transposed', ctypes.c_bool),
                ('slice_detection_method', ctypes.c_char_p),
                ('slice_detection_range', ctypes.c_char_p),
                ('slice_detection_param', ctypes.c_double),
                ]


def ameimportdata(filename, **read_params):
    """
    Use this function to read table data from text (*.txt, *.csv) or spreadsheet
    files (*.xlsx), and organize them into a table layout recognized by Amesim.
    Values read using this function can be written to an Amesim specific file
    (*.data) using the ameexportdata function, or one of the table-specific
    functions (amewrite1dtabletofile, amewrite2dtabletofile,
    amewritem1dtabletofile, amewritexytabletofile).
    This is similar to amereadtextfile and amereadspreadsheetfile, but is more
    convenient to use since it uses only keyword arguments (instead of
    positional arguments).
    A summary of the output format returned by this function is given below.
    For a detailed explanation of the table formats, please consult the Amesim
    manual.

    1D Tables
    =========
    The general structure of a 1D table is:
        x=[x_1, x_2, ..., x_N]  # x-axis, length N
        y=[y_1, y_2, ..., y_N]  # y-axis, length N

    1D tables can be seen as a special case of XY tables, having a single y axis.

    Example:
    --------
    A simple example of reading a 1D table from a custom format file that looks
        like that:
        Index Value
        0 5
        1 4
        2 3
        3 2
        4 1
        >>  values = ameimportdata('C:/data/input/1d_table.txt',
                table_type='1d', header_row=1, selection='A1:B6')
        >>  print values['x']
            [0, 1, 2, 3, 4]
        >>  print values['y']
            [5, 4, 3, 2, 1]
        >>  print values['header']
            ['Index', 'Value']

    XY Tables
    =========
    An XY table represents multi-column table, or multiple columns of values
    (Y-axes) associated to a single column (X-axis).
    The general structure of an XY table is:
        xys=[[x_1, x_2, ..., x_N],     # the x-axis values, length N
             [y1_1, y1_2, ..., y1_N],  # the y1-axis values, length N
             [y2_1, y2_2, ..., y2_N],  # the y2-axis values, length N
             ...,
             [yM_1, yM_2, ..., yM_N]]  # the yM-axis values, length N

    Example:
    --------
    A simple example of reading an XY table from a text file with this content:
        X;Y1;Y2
        0.1;1;9
        0.2;2;8
        0.3;3;7
        0.4;4;6
        0.5;5;5
        0.6;6;4

        >>  values = ameimportdata('C:/data/input/xy_table.csv', table_type='xy', 
                delimiter=';', selection='A3:A5 C3:C5', header_row=1)
        >>  print(values['xys'])
                [[0.2, 0.3, 0.4], [8, 7, 6]]
        >>  print(values['header'])
                ['X', 'Y2']

    2D Tables
    =========
    A 2D table represents a rectangular mesh of length NxM, given by y=(x1,x2).
    The general structure of a 2D table is:
        x1=[x1_1, x1_2, ... x1_N]    # x1 axis, length N
        x2=[x2_1, x2_2, ... x2_M]    # x2 axis, length M
        y=[[y_1, y_2, ..., y_N],
            ...,
           [y_1, y_2, ..., y_MN]]    # y axis, length MxN, contains values for
                                     # each combination of x1 with x2 values

    Example:
    --------
    Reading a sample 2D table from a file that looks like this:
        0;1;2;3;4;5;6

        0;3;2;2;2;2;2;3
        1;3;4;4;5;4;4;3
        2;3;2;2;2;2;2;3

        >>  values = ameimportdata('C:/data/input/2d_table.data',
                table_type='2d', selection={'x1':1, 'x2':'A3:A', 'y':'B3:'})
        >>  print(values['x1'])
                [0, 1, 2, 3, 4, 5, 6]
        >>  print(values['x2'])
                [0, 1, 2]
        >>  print(values['y'])
                [[3, 2, 2, 2, 2, 2, 3], [3, 4, 4, 5, 4, 4, 3], [3, 2, 2, 2, 2, 2, 3]]

    M1D Tables
    ==========
    An M1D table is a set of multiple 1D tables, each table being called a "slice"
    of the M1D table. Each slice can have a different length. The number of slices
    and the length of each slice is given by the X2 axis of the M1D table.
    The general structure of an M1D table is:
        x2=[x2_1, x2_2, x2_3, ..., x2_N]         # N slices
        x1=[[x1_s1_1, x1_s1_2, ..., x1_s1_s1M],  # x1-axis, slice 1, length M
            [x1_s2_1, x1_s2_2, ..., x1_s2_s2N],  # x1-axis, slice 2, length N
            ...,
            [x1_sN_1, x1_sN_2, ..., x1_sN_sNO]]  # x1-axis, slice N, length O
        y= [[y_s1_1, y_s1_2, ..., y_s1_s1M],     # y-axis, slice 1, length M
            [y_s2_1, y_s2_2, ..., y_s2_s2N],     # y-axis, slice 2, length N
            ...,
            [y_sN_1, y_sN_2, ..., y_sN_sNO]]     # y-axis, slice N, length O

    Example:
    --------
    Reading an M1D table from a file that looks like that:
        Slice 
        0;1;5
        0;2;4
        0;3;3
        0;4;2
        0;5;1
        1;1;5
        1;2;4
        1;3;3
        2;1;7
        2;2;6
        2;3;5
        2;4;4
        2;5;3
        2;6;2
        2;7;1

        >>  values = ameimportdata('C:/data/input/m1d_table.txt',
                table_type='m1d', slice_detection_method='x2_cycle')
        >>  print(values['x1'])
                [[1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]]
        >>  print(values['x2'])
                [0.0, 1.0, 2.0]
        >>  print(values['y'])
                [[5.0, 4.0, 3.0, 2.0, 1.0], [5.0, 4.0, 3.0], [7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]]
    Inputs:
    =======
    Positional arguments:
    filename                  : the file that will be read. It can represent a
        file name (assumed to be located in the current directory), or a full
        path to a file.

    Keyword arguments:
    table_type                : the table layout to be used when reading the
        values in the table. Possible values are: '1d', '2d', 'xy', 'm1d'.
    selection                 : a string representing the data range to be 
        imported, given in the form of
        (LeftColumn)(FirstRow):(RightColumn)(LastRow), all parts being optional.
        One such selection can look like 'A3:B100' and means that only values
        between column A, row 3 and column B row 100 will be imported.
        Another selection string could look like 'C:E', and means that only
        data between columns C and E will be imported.
        For 2D tables, it is possible to define selections for each axis of the
        table. In that case, the selection string can be a dictionary with keys
        representing the table axis ('x1', 'x2', 'y'). The value of each key is
        a regular selection string. For example, the following selection could
        be specified for a 2D table:
        >>  selection={'x1':'B1:F1', 'x2':'A2:A100', 'y':'B2:G100'}
        For M1D tables, the selection allows to specify multiple M1D slices by
        separating them with the '/' (forward-slash) character. For example,
        the following selection could be specified for defining the 3 slices of
        an M1D table:
        >>  selection='2:5 / 6:10 / 13:80'
        Moreover, each slice can contain multiple selection by separating the
        values within the slice with a space:
        >>  selection='2:3 4:5 / 6:10 11:12 / 13:50 51:60 61:80'
        Moreover, each M1D slice can specify the selection for the X2 axis
        separately by adding the '[x2]' prefix to the selection.
        The following is a selection for 2 slices, with values for the X2 axis
        given separately from the values of X1 and Y axis:
        >>  selection='[x2]A1; B1:B10 E1:E10 / [x2]A11; B11:B20 E11:E20'
    header_row                : the row number where the header of the table is
        found.
    units_row                 : the row number where the units of the values in
        the table are found.
    delimiter                 : the character or string used for
        delimiting the columns of the table. If no delimiter is specified, then
        the function tries to detect it automatically.
    skip_duplicate_delimiters : if set to true, then multiple
        adjacent delimiters are considered only one. Setting this to true can
        change the number of columns detected.
    column_width              : a scalar value that represents the width of
        each column in fixed width files (all file rows have the same length).
        When using this value (while leaving the delimiter parameter empty),
        each column is considered to consist of exactly column_width characters.
    transposed                : specify whether the table is transposed after
        it is read from the file. The transposition is done before using
        the selection, header row or units row information.
    sheet_index               : the index of the sheet that holds the table
        data. The first index is 1. Used only if the input file is a spreadsheet
        file with extension *.xlsx.  
    sheet_name                : the name of the sheet that holds the table data.
        Used only if the input file is a spreadsheet file with extension *.xlsx.
    slice_detection_method    : used for M1D tables to specify how slices are
        detected. Possible values are 'slice_length', 'x1_cycle' and
        'x2_ximilarity'.
    slice_detection_range     : used only if slice_detection_method parameter
        is set. Set this parameter to limit the slice detection to a specific
        range.
    slice_detection_param     : used only if slice_detection_method parameter
        is set.
        If the detection method is 'slice_length', then this parameter specifies
        the number of rows in each slice.
        If the detection method is 'x1_cycle', then this parameter specifies
        a tolerance value when comparing consecutive x1 values.
        If the detection method is 'x2_similarity', then this parameter
        specifies a tolerance value when comparing consecutive x2 values.

    Outputs:
    ========
    A dictionary with keys depending on the table type.
    Common keys for all table types:
        header : a list of strings holding the values of the header row.
            For XY and 1D tables, the order of the header values corresponds to
            axes 'X', 'Y1', 'Y2', ... 'Yn', in that order.
            For 2D tables, the order of the header values corresponds to axes
            'X1', 'X2', 'Y', in that order.
            For M1D tables, the order of the header values corresponds to axes
            'X2', 'X1', 'Y', in that order.
        units : a list of strings holding the values of the header row.
            For XY and 1D tables, the order of the units corresponds to axes
            'X', 'Y1', 'Y2', ... 'Yn', in that order.
            For 2D tables, the order of the units corresponds to axes
            'X1', 'X2', 'Y', in that order.
            For M1D tables, the order of the units corresponds to axes
            'X2', 'X1', 'Y', in that order.
        table_type : a string that specifies the type of the table, with
            possible values: '1d', 'xy', '2d', 'm1d'
    The keys for XY tables:
        xys : a list of lists of numbers holding the values for each column of
            the table
    The keys for 1D tables:
        x : a list of numbers holding the X-axis values.
        y : a list of numbers holding the Y-axis values.
    The keys for 2D tables:
        x1 : a list of numbers holding the X1-axis values.
        x2 : a list of numbers holding the X2-axis values.
        y : a list of lists of numbers holding the Y-axis values.
    The keys for M1D tables:
        x1 : a list of lists of numbers holding the X1-axis values.
        x2 : a list of numbers holding the X2-axis values.
        y : a list of lists of numbers holding the Y-axis values.
    """

    def _valid_params():
        return [
            'selection',
            'table_type',
            'header_row',
            'units_row',
            'delimiter',
            'skip_duplicate_delimiters',
            'column_width',
            'transposed',
            'sheet_index',
            'sheet_name',
            'slice_detection_method',
            'slice_detection_range',
            'slice_detection_param',
        ]

    funcname = read_params.get('function', ameimportdata.__name__)
    dimutils.validate_params(funcname, _valid_params(), read_params)
    if not isinstance(filename, str):
        raise AMESimError(funcname, 'Filename input parameter "{}" is not a string'.format(filename))
    if not os.path.isabs(filename):
        filename = os.path.join(os.getcwd(), filename)
    if not os.path.isfile(filename):
        raise AMESimError(funcname, 'File "{}" does not exist'.format(filename))

    # Prepare parameters
    import_data = scripting_api.importData
    import_data.argtypes = [ctypes.POINTER(__ReadFileParams), ctypes.POINTER(__FileData),
                            ctypes.POINTER(ctypes.c_char_p)]
    c_values = __FileData()
    c_read_params = __ReadFileParams()
    c_read_params.filename = dimutils.convert_str_py2c(filename)

    selection = read_params.get('selection', None)
    if type(selection) is list:
        selection_str = ';'.join(selection)
    elif type(selection) is dict:
        selection_list = []
        for k, v in selection.items():
            if k not in ['x1', 'x2', 'y']:
                raise AMESimError(funcname,
                                  'unknown selection key: {} in selection dictionary {}.'.format(k, selection))
            selection_list.append('[{}]{}'.format(k, v))
        selection_str = ';'.join(selection_list)
    else:
        selection_str = selection
    c_read_params.selection = dimutils.convert_str_py2c(selection_str)
    c_read_params.table_type = dimutils.convert_str_py2c(read_params.get('table_type', 'xy'))
    header_row = read_params.get('header_row', -1)
    if header_row > 0:
        header_row -= 1
    else:
        header_row = -1
    c_read_params.header_row = header_row
    units_row = read_params.get('units_row', -1)
    if units_row > 0:
        units_row -= 1
    else:
        units_row = -1
    c_read_params.units_row = units_row
    c_read_params.delimiter = dimutils.convert_str_py2c(read_params.get('delimiter', ''))
    c_read_params.multiple_delimiters_as_one = read_params.get('skip_duplicate_delimiters', True)
    c_read_params.column_width = read_params.get('column_width', -1)
    c_read_params.transposed = read_params.get('transposed', False)
    c_read_params.sheet_index = read_params.get('sheet_index', -1)
    c_read_params.sheet_name = dimutils.convert_str_py2c(read_params.get('sheet_name', ''))
    c_read_params.slice_detection_method = dimutils.convert_str_py2c(read_params.get('slice_detection_method', ''))
    c_read_params.slice_detection_range = dimutils.convert_str_py2c( read_params.get('slice_detection_range', ''))
    c_read_params.slice_detection_param = read_params.get('slice_detection_param', 0.0)

    # Call the native function
    c_error_message = ctypes.c_char_p()
    ret_code = import_data(ctypes.byref(c_read_params), ctypes.byref(c_values), ctypes.byref(c_error_message))

    # Error Checking
    if ret_code != 0:
        error = AMESimError(funcname, dimutils.convert_str_c2py(c_error_message))
        assert (len(c_error_message.value) > 0)
        scripting_api.releaseMemory_charPtr(c_error_message)
        raise error
    # end of error checking

    # Convert values to standard Python types
    table_type = dimutils.convert_str_c2py(c_read_params.table_type).lower()
    if table_type == '1d':
        nb_rows = c_values.data_lengths[0]
        nb_cols = c_values.data_lengths[1]
        x_values, y_values = dimutils.convert_table1d_c2py(c_values.data, nb_rows)
        header = dimutils.convert_list_c2py(c_values.header, nb_cols if header_row > -1 else 0)
        units = dimutils.convert_list_c2py(c_values.units, nb_cols if units_row > -1 else 0)
        values = {'x': x_values, 'y': y_values, 'header': header, 'units': units, 'table_type': '1d'}
    elif table_type == 'xy':
        nb_rows = c_values.data_lengths[0]
        nb_cols = c_values.data_lengths[1]
        tablexy = dimutils.convert_matrix_c2py(c_values.data, nb_rows, nb_cols)
        header = dimutils.convert_list_c2py(c_values.header, nb_cols if header_row > -1 else 0)
        units = dimutils.convert_list_c2py(c_values.units, nb_cols if units_row > -1 else 0)
        values = {'xys': tablexy, 'header': header, 'units': units, 'table_type': 'xy'}
    elif table_type == '2d':
        x1_axis, x2_axis, y_axis = dimutils.extract_2d_table_c2py(c_values)
        nb_rows = 1
        nb_cols = 3
        header = dimutils.convert_list_c2py(c_values.header, nb_cols if header_row > -1 else 0)
        units = dimutils.convert_list_c2py(c_values.units, nb_cols if units_row > -1 else 0)
        values = {'x1': x1_axis, 'x2': x2_axis, 'y': y_axis, 'header': header, 'units': units, 'table_type': '2d'}
    elif table_type == 'm1d':
        x2_values, x1_values, y_values = dimutils.extract_m1d_table_c2py(c_values)
        nb_rows = 1
        nb_cols = 3
        header = dimutils.convert_list_c2py(c_values.header, nb_cols if header_row > -1 else 0)
        units = dimutils.convert_list_c2py(c_values.units, nb_cols if units_row > -1 else 0)
        values = {'x1': x1_values, 'x2': x2_values, 'y': y_values, 'header': header, 'units': units,
                  'table_type': 'm1d'}
    else:
        nb_rows = nb_cols = 1
        values = None

    # Release memory
    scripting_api.releaseMemory_structMembers(ctypes.byref(c_read_params), ctypes.byref(c_values), nb_rows, nb_cols)

    return values


def amereadtextfile(filename, delimiter='', skip_duplicate_delimiters=False, column_width=-1, **kwargs):
    """amereadtextfile 
    Parse the given file, extract and return data according to the given
    parameters.
    values = amereadtextfile(filename, delimiter, skip_duplicate_delimiters,
        column_width, kwargs)

    This function is just a proxy for function ameimportdata and is here
    for compatibility purpose only.
    Please consult the help of ameimportdata for the full list of inputs, outputs,
    and usage examples.

    Inputs:
    =======
    filename : the name of the file to read data from.
    delimiter : (optional) the character or string used for delimiting the
        columns of the table. If no delimiter is specified, then the function
        tries to detect it automatically. 
    skip_duplicate_delimiters : (optional) if set to true, then multiple
        adjacent delimiters are considered only one. Setting this to true can
        change the number of columns detected.
    column_width : (optional) a scalar value that represents the width of
        each column in fixed width files (all file rows have the same length).
        When using this value (while leaving the delimiter parameter empty),
        each column is considered to consist of exactly COLUMNWIDTH
        characters.

    Outputs:
    ========
    See the output of ameimportdata.
   
    Examples:
    =========
    values = amereadtextfile('inputfile.txt', selection='A2:D');
    Read data from the file between the first column and the fourth column,
    starting from row 2.  No header row or units row is defined, so they are
    not retrieved. The delimiter is automatically detected.

    values = amereadtextfile('inputfile.csv', ',', False, selection='B:D100', transposed=True);
    Read data from the file between the second column and the fourth column,
    up to row 100. No header row is defined, but the units row is specified
    and thus retrieved.  The delimiter is also specified as being ','
    (comma), and the resulted table is transposed after being read from the
    file.
    """
    function_name = amereadtextfile.__name__
    read_params = {
        'function': function_name,
        'delimiter': delimiter,
        'skip_duplicate_delimiters': skip_duplicate_delimiters,
        'column_width': column_width
    }
    read_params.update(kwargs)
    try:
        return ameimportdata(filename, **read_params)
    except AMESimError as err:
        raise AMESimError(function_name, err.error)
    except Exception as e:
        print(e)
        raise


def amereadspreadsheetfile(filename, sheet_index=-1, sheet_name='', **kwargs):
    """amereadspreadsheetfile
    Parse the given file, extract and return data according to the given
    parameters.
    values = amereadspreadsheetfile(filename, sheet_index, sheet_name, kwarsgs)

    This function is just a proxy for function ameimportdata and is here
    for compatibility purpose only.
    Please consult the help of ameimportdata for the full list of inputs, outputs,
    and usage examples.

    Inputs:
    =======
    filename : the name of the file to read data from.
    sheet_index : the index of the sheet that hodls the table data. The
        first index is 1.
    sheet_name : the name of the sheet that holds the table data.

    Outputs:
    =======
    See the outputs of function ameimportdata.
   
    Examples:
    =========
    values = amereadspreadsheetfile('inputfile.xlsx');
        Read values from the first sheet of file 'inputfile.xlsx'.

    values = amereadspreadsheetfile('inputfile.xlsx', 2);
        Read values from sheet 2 of file 'inputfile.xlsx'
        
    values = amereadspreadsheetfile('inputfile.xlsx', -1,
        'values_sheet', selection='B:D', header_row=1, units_row=2);
        Read values from sheet named 'values_sheet' of file 'inputfile.xlsx',
        and limit the selection to columns B, C and D. The header row is set to
        1, and the units row to 2.
    """
    if sheet_index == -1 and not sheet_name:
        sheet_index = 1

    function_name = amereadspreadsheetfile.__name__
    read_params = {
        'function': function_name,
        'sheet_index': sheet_index,
        'sheet_name': sheet_name,
    }
    read_params.update(kwargs)

    try:
        return ameimportdata(filename, **read_params)
    except AMESimError as err:
        raise AMESimError(function_name, err.error)


def __writeDataToFile_init_argtypes(wdtf):
    filename_type = ctypes.c_char_p
    values_type = ctypes.POINTER(ctypes.c_double)
    nb_cols_type = ctypes.c_int
    nb_rows_type = ctypes.c_int
    header_type = ctypes.POINTER(ctypes.c_char_p)
    units_type = ctypes.POINTER(ctypes.c_char_p)
    error_message_type = ctypes.POINTER(ctypes.c_char_p)

    wdtf.argtypes = [filename_type,
                     values_type,  # many data sets
                     nb_rows_type,
                     nb_cols_type,
                     header_type,
                     units_type,
                     error_message_type]


def amewrite1dtabletofile(filename, x, y, header=None, units=None):
    """
    Write the two given vectors in a .data file as a 1D Amesim table.

    Inputs:
    =======
    filename : the file name where the XY table will be written.
    x : the list of numbers that represent the X axis of the table.
    y : the list of numbers that represent the Y axis of the table.
    header : a list of strings that represents comments associated with each
        column of the table (e.g. variable names)
    units : a list of strings that represents units of variables associated with
        each column of the table.

    Example:
    ========
    >>  filename = '/path/to/file.data'
    >>  x = [1, 2, 3]
    >>  y = [4, 5, 6]
    >>  header = ['header1', 'header2']
    >>  units  = ['unit1', 'unit2']
    >>  amewritexytabletofile(filename, x, y, header, units)
    """
    units = units or []
    header = header or []
    function_name = amewrite1dtabletofile.__name__
    write_params = {
        'function': function_name,
        'table_type': '1d',
        'x': x,
        'y': y,
        'units': units,
        'header': header
    }
    try:
        return ameexportdata(filename, **write_params)
    except AMESimError as err:
        raise AMESimError(function_name, err.error)
    except Exception as e:
        print(e)
        raise


def amewritexytabletofile(filename, values, header=None, units=None):
    """
    Write the given list of lists of numbers into a .data file as an XY
    Amesim table.

    Inputs:
    =======
    filename : the file name where the XY table will be written.
    values : the list of list of numbers that represent the XY columns.
    header : a list of strings that represents comments associated with each
        column of the XY table (e.g. variable names)
    units : a list of strings that represents units of variables associated with
        each column of the XY table.

    Example:
    ========
    >>  filename = '/path/to/file.data'
    >>  values = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    >>  header = ['col1', 'col2', 'col3']
    >>  units  = ['unit1', 'unit2', 'unit3']
    >>  amewritexytabletofile(filename, values, header, units)
    """
    units = units or []
    header = header or []
    function_name = amewritexytabletofile.__name__
    write_params = {
        'function': function_name,
        'table_type': 'xy',
        'xy': values,
        'units': units,
        'header': header
    }
    try:
        return ameexportdata(filename, **write_params)
    except AMESimError as err:
        raise AMESimError(function_name, err.error)
    except Exception as e:
        print(e)
        raise


def amewrite2dtabletofile(filename, x1, x2, y, header=None, units=None):
    """
    Write the given values into a .data file as a 2D Amesim table.
    This is a dedicated writing funtion for 2D tables. For a more general and
    flexible function, see ameexportdata.

    Inputs:
    =======
    filename : the output .data file name or full path.
    x1 : a list of numbers representing the X1 axis of a 2D table.
    x2 : a list of numbers representing the X2 axis of a 2D table.
    y  : a list of list of numbers representing the Y axis of a 2D table.
    header : a list of strings of length 3 that specifies a comment associated
        to each axis of the table (e.g. a variable name).
    units : a list of strings of length 3 that specifies the unit associated
        to each axis variable of the table.

    Example:
    ========
    >>  x1 = [1, 2, 3]
    >>  x2 = [0, 1, 2, 3, 4, 5]
    >>  y  = [ \
            [1, 2, 3], \
            [4, 5, 6], \
            [7, 8, 9], \
            [10, 11, 12], \
            [13, 14, 15], \
            [16, 17, 18], \
            [19, 20, 21] \
        ]
    >>  header = ['header1', 'header2', 'header3']
    >>  units = ['unit1', 'unit2', 'unit3']
    >>  amewrite2dtabletofile(filename, x1, x2, y, header, units)
    """
    units = units or []
    header = header or []
    function_name = amewrite2dtabletofile.__name__
    write_params = {
        'function': function_name,
        'table_type': '2d',
        'x1': x1,
        'x2': x2,
        'y': y,
        'units': units,
        'header': header
    }
    try:
        return ameexportdata(filename, **write_params)
    except AMESimError as err:
        raise AMESimError(function_name, err.error)
    except Exception as e:
        print(e)
        raise


def amewritem1dtabletofile(filename, x1, x2, y, header=None, units=None):
    """
    Write the given values into a .data file as an M1D Amesim table.

    Inputs:
    =======
    filename : the file where the M1D table will be written.
    x1 : a list of list of numbers that represent the values on the X1
        axis of the table, grouped by slices.
    x1 : a list numbers that represent the values on the X2 axis of the table.
    y : a list of list of numbers that represent the values on the Y axis
        of the table, grouped by slices.
    header : a list of string of length 3, representing comments associated
        with each axis of the table (e.g. variable names)
    units : a list of strings of length 3, representing the units associated
        to axis variables.

    Example:
    ========
    >>  filename = '/path/to/file.data'
    >>  x2 = [0, 1, 2]
    >>  x1 = [[1, 2, 3, 4], [1, 2], [1, 2, 3]]
    >>  y = [[1, 2, 3, 4], [1, 2], [1, 2, 3]]
    >>  header = ['h1', 'h2', 'h3']
    >>  units = ['u1', 'u2', 'u3']
    >>  amewritem1dtabletofile(filename, x1, x2, y, header, units)
    """
    units = units or []
    header = header or []
    function_name = amewritem1dtabletofile.__name__
    write_params = {
        'function': function_name,
        'table_type': 'm1d',
        'x1': x1,
        'x2': x2,
        'y': y,
        'units': units,
        'header': header
    }
    try:
        return ameexportdata(filename, **write_params)
    except AMESimError as err:
        raise AMESimError(function_name, err.error)
    except Exception as e:
        print(e)
        raise


def amewritetodatafile(filename, values, header=None, units=None, **kwargs):
    r"""amewritetodatafile 
    Write the given column vectors, and optionally the header and units, into
    the specified filename, in the format of a Amesim specific table type (1D
    for table with 2 columns, and XY table for tables of 1, 3 or more columns).

    amewritetodatafile(filename, selection, headerrow, unitsrow, transposed,
    delimiter, multipledelimitersasone, columnwidth)
   
    Inputs:
    =======
    filename    : the name of the file where data is written. If the file
        already exists, it is overwritten.
    values      : the values to be written into the file.
    header      : (optional) the header of the table that will be written
        into the file.
    units       : (optional) the units of the variables on each column of
        the table.

    Examples:
    ========
    Create a 3-column table:
        >> values = [[2 5 2], [3 1 7]]
   
    Write it to a file:
        >> amewritetodatafile(r'C:\data\out_file.data', values);
     
    Verify that the values were written correctly into the file:
        >> amereadtextfile(r'C:\data\out_file.data')
             2     5     2
             3     1     7
    """
    units = units or []
    header = header or []
    function_name = amewritetodatafile.__name__
    write_params = {
        'function': function_name,
        'header': header,
        'units': units
    }

    user_set_table_type = 'table_type' in kwargs
    if user_set_table_type:
        write_params['table_type'] = kwargs['table_type']
    else:
        if len(values) == 2:
            write_params['table_type'] = '1d'
        else:
            write_params['table_type'] = 'xy'

    if type(values) is dict:
        write_params.update(values)
    elif type(values) is list:
        if write_params['table_type'] == 'xy':
            write_params['xys'] = values
        elif write_params['table_type'] == '1d':
            write_params['x'] = values[0]
            write_params['y'] = values[1]
        else:
            write_params['table_type'] = 'xy'
            write_params['xys'] = values

    try:
        return ameexportdata(filename, **write_params)
    except AMESimError as err:
        raise AMESimError(function_name, err.error)
    except Exception as e:
        print(e)
        raise


class __WriteFileParams(ctypes.Structure):
    _fields_ = [('filename', ctypes.c_char_p),
                ('table_type', ctypes.c_char_p),
                ]


def ameexportdata(filename, **write_params):
    r"""ameexportdata
    Use this function to write table data to an Amesim recognized file (*.data).
    This is similar to amewritetodatafile, but can work with any of the supported
    table types: '1D', 'XY', '2D', 'M1D'. A summary of the input format expected
    for the different table types is given below. For a detailed explanation of
    these table formats, please consult the Amesim manual.
    Compared to amewritetodatafile function, this function is also more flexible
    in the way it receives the input parameters, since they are keyword arguments
    instead of positional arguments.

    1D Tables
    =========
    The general structure of a 1D table is:
        x=[x_1, x_2, ..., x_N]  # x-axis, length N
        y=[y_1, y_2, ..., y_N]  # y-axis, length N

    1D tables can be seen as a special case of XY tables, having a single y axis.
    For a 1D table specific writing function, see amewrite1dtabletofile

    Example:
    --------
    A simple example of a 1D table written to a file:
        x=[1, 2, 3]   # the x axis, sorted in ascending order
        y=[2, 7, 9]   # the y axis
        # write using the dedicated x and y axes arguments
        ameexportdata('C:/data/output/1d_table.data', table_type='1d', x=x, y=y)
        # or write using the general values argument
        ameexportdata('C:/data/output/1d_table.data', table_type='1d', values={'x':x, 'y':y})

    XY Tables
    =========
    An XY table represents multi-column table, or multiple columns of values
    (Y-axes) associated to a single column (X-axis).
    The general structure of an XY table is:
        xys=[[x_1, x_2, ..., x_N],     # the x-axis values, length N
             [y1_1, y1_2, ..., y1_N],  # the y1-axis values, length N
             [y2_1, y2_2, ..., y2_N],  # the y2-axis values, length N
             ...,
             [yM_1, yM_2, ..., yM_N]]  # the yM-axis values, length N

    For a XY table specific writing function, see amewritexytabletofile

    Example:
    --------
    A sample XY table with two y axes could look like this:
        xys=[[0, 1, 2, 3],         # the x axis, sorted in ascending order
             [8, -2, 3, 1.4],      # the y1 axis
             [-5.3, 8, 12, 9]]     # the y2 axis
        # Write using the dedicated xys argument
        ameexportdata('C:/data/xy_table.data', table_type='xy', xys=xys)
        # or using the general values argument
        ameexportdata('C:/data/xy_table.data', table_type='xy', values={'xys':xys})

    2D Tables
    =========
    A 2D table represents a rectangular mesh of length NxM, given by y=(x1,x2).
    The general structure of a 2D table is:
        x1=[x1_1, x1_2, ... x1_N] # x1 axis, lenght N
        x2=[x2_1, x2_2, ... x2_M] # x2 axis, length M
        y=[[y_1_1, y_1_2, ..., y_1_N],
            ...,
           [y_M_1, y_M_2, ..., y_M_N]] # y axis, length MxN, contains values for
                                       # each combination of x1 with x2 values

    For a 2D table specific writing function, see amewrite2dtabletofile

    Example:
    --------
    Writing a 2D table could look like this:
        x1=[0, 1, 2, 3]        # the x1 axis, ordered
        x2=[100, 200, 300]     # the x2 axis, ordered
        y= [[1, 2, 3, 4],      # the y axis, with values for each pair of x1,x2
            [5, 6, 7, 8],
            [9, 10, 11, 12]]
        # Write using the dedicated x1, x2 and y axes arguments:
        ameexportdata('C:/data/2d_table.data', table_type='2d', x1=x1, x2=x2, y=y)
        # or using the general values argument:
        ameexportdata('C:/data/2d_table.data', table_type='2d', values={'x1':x1, 'x2':x2, 'y':y})

    M1D Tables
    ==========
    An M1D table is a set of multiple 1D tables, each table being called a "slice"
    of the M1D table. Each slice can have a different length. The number of slices
    and the length of each slice is given by the X2 axis of the M1D table.
    The general structure of an M1D table is:
        x2=[x2_1, x2_2, x2_3, ..., x2_N]         # N slices
        x1=[[x1_s1_1, x1_s1_2, ..., x1_s1_s1M],  # x1-axis, slice 1, length M
            [x1_s2_1, x1_s2_2, ..., x1_s2_s2N],  # x1-axis, slice 2, lenght N
            ...,
            [x1_sN_1, x1_sN_2, ..., x1_sN_sNO]]  # x1-axis, slice N, length O
        y= [[y_s1_1, y_s1_2, ..., y_s1_s1M],     # y-axis, slice 1, length M
            [y_s2_1, y_s2_2, ..., y_s2_s2N],     # y-axis, slice 2, lenght N
            ...,
            [y_sN_1, y_sN_2, ..., y_sN_sNO]]     # y-axis, slice N, length O

    For a M1D table specific writing function, see amewritem1dtabletofile

    Example:
    --------
    A sample M1D table cold look like this:
        x1=[100, 200, 300]       # x1 axis, one value for each slice
        x2=[[0, 1],              # x2 axes, one set of values for each slice
            [0, 1, 2, 3, 4, 5],
            [4, 5, 6]]
        y= [[10, 20],            # y axes, one set of values for each slice
            [9, 8, 7, 6, 5, 4],
            [1, 2, 3]]
        # Write using the dedicated x1, x2 and y axes arguments:
        ameexportdata('C:/data/outpu/m1d_table.data', table_type='m1d', x1=x1, x2=x2, y=y)
        # or using the general values argument.
        ameexportdata('C:/data/outpu/m1d_table.data', table_type='m1d', values={'x2':x2, 'x1':x1, 'y':y})

    Inputs:
    =======
    Positional arguments:
    filename    : the file where the data will be written. It can represent
                  a file name (assumed to be located in the current directory),
                  or a full path to a file.

    Keyword arguments:
    table_type  : the table layout to be used when writing the values.
                  It is a string with possible values: '1d', '2d', 'xy', 'm1d'.
    values      : A dictionary containing lists needed by the table type, each
                  component of the dictionary defining an axis of the table.
                  This argument is mandatory if values are not given thorough the
                  dedicated axis parameters (described below).
    x           : Valid only if table_type is '1d', and represents the x-axis
                  values of the table.
                  x=[x_1, x_2, ..., x_n]
    y           : Valid only if table_type is '1d', '2d' or 'm1d', and 
                  is a vector of numbers representing the y axis of the table.
                  See the specific table description above for the exact layout 
                  expected for this argument.
    x1          : Valid only if table_type is '2d' or 'm1d', and is a vector
                  of numbers representing the values on the x1-axis of the
                  table.
                  See the specific table description above for the exact layout 
                  expected for this argument.
    x2          : Valid only if table_type is '2d' or 'm1d', and is a vector
                  of numbers representing the values on the x2-axis of the
                  table.
                  See the specific table description above for the exact layout 
                  expected for this argument.
    xys         : Valid only if the table_type is 'xy', and is a vector of
                  vectors of numbers, each vector representing an axis
                  [[x-axis], [y1-axis], [y2-axis] ... [yn-axis]]
    header      : A list of strings representing comments associated to each
                  column in the table.
    units       : A list of strings representing units for variables associated
                  to each column in the table.
    """

    def _valid_params():
        return [
            'values',
            'table_type',
            'x',
            'y',
            'x1',
            'x2',
            'xys',
            'header',
            'units',
        ]

    funcname = write_params.get('function', ameexportdata.__name__)
    dimutils.validate_params(funcname, _valid_params(), write_params)
    if not isinstance(filename, str):
        raise AMESimError(funcname, 'Filename input parameter "{}" is not a string'.format(filename))

    if not os.path.isabs(filename):
        filename = os.path.join(os.getcwd(), filename)

    table_type = write_params.get('table_type', 'xy')

    # Prepare C parameters
    export_data = scripting_api.exportData
    export_data.argtypes = [ctypes.POINTER(__WriteFileParams), ctypes.POINTER(__FileData),
                            ctypes.POINTER(ctypes.c_char_p)]
    c_values = __FileData()
    c_write_params = __WriteFileParams()
    c_write_params.filename = dimutils.convert_str_py2c(filename)
    c_write_params.table_type = dimutils.convert_str_py2c(table_type)

    if table_type == '1d':
        x_values = write_params.get('x', [])
        y_values = write_params.get('y', [])

        values = [x_values, y_values]
        x_not_found = not isinstance(x_values, list) or not x_values
        y_not_found = not isinstance(y_values, list) or not y_values
        if x_not_found or y_not_found:
            values_dict = write_params.get('values', {})
            x_values = values_dict['x']
            y_values = values_dict['y']
            values = [x_values, y_values]

        if not isinstance(values, list) or not values:
            raise AMESimError(funcname,
                              'Invalid input values provided: "{}". The list of values is empty or not'
                              ' a list of numbers.'.format(values))

        # Make sure all vectors are the same length
        nb_rows = len(values[0])
        dimutils.ensure_minimum_width(values, nb_rows, 0)
        c_values.data, nb_rows, nb_cols = dimutils.convert_matrix_py2c(values)
        c_values.data_lengths = dimutils.convert_list_py2c([nb_rows, nb_cols], ctypes.c_int)

    if table_type == 'xy':
        values = write_params.get('xys', [])

        if not isinstance(values, list) or not values:
            values_dict = write_params.get('values', {})
            values = values_dict.get('xys', [])

        if not isinstance(values, list) or not values:
            raise AMESimError(funcname,
                              'No data input provided. You must provide an non-empty list of numbers.'.format(values))

        # Make sure all vectors are the same length
        nb_cols = len(values)
        nb_rows = max(len(values[col]) for col in range(0, nb_cols))
        dimutils.ensure_minimum_width(values, nb_rows, 0)
        c_values.data, nb_rows, nb_cols = dimutils.convert_matrix_py2c(values)
        c_values.data_lengths = dimutils.convert_list_py2c([nb_rows, nb_cols], ctypes.c_int)

    elif table_type == '2d':
        x1_values = write_params.get('x1', [])
        x2_values = write_params.get('x2', [])
        y_values = write_params.get('y', [])

        x1_not_found = not isinstance(x1_values, list) or not x1_values
        x2_not_found = not isinstance(x2_values, list) or not x2_values
        y_not_found = not isinstance(y_values, list) or not y_values

        if x1_not_found or x2_not_found or y_not_found:
            values_dict = write_params.get('values', {})
            x1_values = values_dict['x1']
            x2_values = values_dict['x2']
            y_values = values_dict['y']

        nb_cols = 3
        c_values.data = dimutils.convert_2d_table_py2c(x1_values, x2_values, y_values)
        c_values.data_lengths = dimutils.convert_list_py2c([len(x1_values), len(x2_values)], ctypes.c_int)

    elif table_type == 'm1d':
        x1_values = write_params.get('x1', [])
        x2_values = write_params.get('x2', [])
        y_values = write_params.get('y', [])

        x1_not_found = not isinstance(x1_values, list) or not x1_values
        x2_not_found = not isinstance(x2_values, list) or not x2_values
        y_not_found = not isinstance(y_values, list) or not y_values

        if x1_not_found or x2_not_found or y_not_found:
            values_dict = write_params.get('values', {})
            x1_values = values_dict['x1']
            x2_values = values_dict['x2']
            y_values = values_dict['y']

        nb_cols = 3
        c_values.data = dimutils.convert_m1d_table_py2c(x1_values, x2_values, y_values)

        nb_slices = len(x1_values)
        slices_lengths = [len(x1_values[slc]) for slc in range(nb_slices)]
        slices_lengths.insert(0, nb_slices)
        c_values.data_lengths = dimutils.convert_list_py2c(slices_lengths, ctypes.c_int)
    else:
        nb_cols = 1

    # prepare the header list
    header = write_params.get('header', [])
    if header:
        dimutils.extend_list(header, nb_cols, "")
    c_values.header = dimutils.convert_list_py2c(header)
    c_values.header_joined = dimutils.convert_str_py2c('\n'.join(header))

    # prepare the units list
    units = write_params.get('units', [])
    if units:
        dimutils.extend_list(units, nb_cols, "")
    c_values.units = dimutils.convert_list_py2c(units)
    c_values.units_joined = dimutils.convert_str_py2c('\n'.join(units))

    # Call the native function
    c_error_message = ctypes.c_char_p()
    ret_code = export_data(ctypes.byref(c_write_params), ctypes.byref(c_values), ctypes.byref(c_error_message))

    # Error Checking
    if ret_code != 0:
        error = AMESimError(funcname, dimutils.convert_str_c2py(c_error_message))
        assert (len(c_error_message.value) > 0)
        scripting_api.releaseMemory_charPtr(c_error_message)
        raise error
    # end of error checking


def __getSheetList_init_argtypes(gslf):
    filename_type = ctypes.c_char_p
    nb_sheets_type = ctypes.POINTER(ctypes.c_int)
    sheet_list_type = ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p))
    error_message_type = ctypes.POINTER(ctypes.c_char_p)

    gslf.argtypes = [filename_type,
                     nb_sheets_type,
                     sheet_list_type,
                     error_message_type]


def amegetsheetlist(filename):
    r"""amegetsheetlist 
    Get the list of sheets that are part of the given (.xlsx) spreadsheet file.
   
    Examples:
    =========
    >> sheets = amegetsheetlist(r'C:\data\my_spreadsheet_file.xlsx')
    >> sheets
        'sheet1'   'sheet2'   'sheet3'
    """
    gslf = scripting_api.getListOfSheets
    __getSheetList_init_argtypes(gslf)

    c_nb_sheets = ctypes.c_int()
    c_sheet_list = ctypes.POINTER(ctypes.c_char_p)()
    c_error_message = ctypes.c_char_p()
    ret_code = gslf(dimutils.convert_str_py2c(filename),
                    ctypes.byref(c_nb_sheets), ctypes.byref(c_sheet_list), ctypes.byref(c_error_message))

    # error checking, will raise if error dll call failed
    if ret_code != 0:
        error = AMESimError("amegetsheetlist", dimutils.convert_str_c2py(c_error_message))
        assert (len(c_error_message.value) > 0)
        scripting_api.releaseMemory_charPtr(c_error_message)
        raise error
    # end of error checking

    sheet_list = dimutils.convert_list_c2py(c_sheet_list, c_nb_sheets.value)
    assert len(sheet_list) == c_nb_sheets.value

    # release memory
    scripting_api.releaseMemory_charPtrPtr(c_sheet_list, c_nb_sheets, True)

    return sheet_list


def amegetsheetcount(filename):
    r"""amegetsheetcount
    Get the number of sheets that are part of the given (.xlsx) spreadsheet
        file.

    Examples:
    =========
    >> sheets = amegetsheetlist(r'C:\data\my_spreadsheet_file.xlsx')
    >> sheets
        'sheet1'   'sheet2'   'sheet3'
    >> sheetCount = amegetsheetcount(r'C:\data\my_spreadsheet_file.xslx')
    >> sheetCount
        3
    """
    return len(amegetsheetlist(filename))
