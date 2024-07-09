# *****************************************************************************
#  This material contains trade secrets or otherwise confidential
#  information owned by Siemens Industry Software Inc. or its
#  affiliates (collectively, "Siemens"), or its licensors. Access to
#  and use of this information is strictly limited as set forth in the
#  Customer's applicable agreements with Siemens.
# 
#  Unpublished work. Copyright 2023 Siemens
# *****************************************************************************
from ctypes import *


def convert_table1d_c2py(c_values, c_nb_rows):
    nb_rows = c_nb_rows  # .value
    x_values = c_values[0:nb_rows]
    y_values = c_values[nb_rows:2 * nb_rows]
    return x_values, y_values


def convert_matrix_c2py(c_values, c_nb_rows, c_nb_cols):
    nb_rows = c_nb_rows  # .value
    nb_cols = c_nb_cols  # .value
    values = []
    first_index = 0
    last_index = nb_rows
    for col in range(0, nb_cols):
        col_values = c_values[first_index:last_index]
        values.append(col_values)
        first_index = last_index
        last_index += nb_rows
    return values


def convert_matrix_py2c(values):
    nb_cols = len(values)
    nb_rows = len(values[0]) if nb_cols > 0 else 0  # assume same length for all rows
    c_values = (c_double * (nb_rows * nb_cols))()
    for row in range(0, nb_rows):
        for col in range(0, nb_cols):
            c_values[row + col * nb_rows] = values[col][row]
    return c_values, nb_rows, nb_cols


def convert_list_c2py(c_values, c_nb_elems):
    nb_elems = c_nb_elems  # .value
    values = [''] * nb_elems
    for elem in range(0, nb_elems):
        c_value = c_values[elem]
        if isinstance(c_value, bytes):  # Need to convert bytes (char* type) to str
            c_value = c_value.decode('utf8')
        values[elem] = c_value
    return values


def convert_list_py2c(values, c_type=c_char_p):
    if not values:
        c_values = None
    else:
        c_values = (c_type * len(values))()
        for idx, elem in enumerate(values):
            if isinstance(elem, str) and c_type == c_char_p:
                elem = elem.encode('utf8')
            c_values[idx] = elem
    return c_values


def convert_str_py2c(py_str):
    if py_str is None:
        return None
    return c_char_p(py_str.encode('utf8'))


def convert_str_c2py(c_str):
    if isinstance(c_str, c_char_p):
        c_str = c_str.value
    return c_str.decode('utf8')


def extend_list(the_list, target_length, fill_value):
    list_length = len(the_list)
    nb_values_to_add = target_length - list_length
    # if nb_values_to_add < 0:
    # raise ValueError('List is already longer than target length')

    the_list.extend([fill_value] * nb_values_to_add)


def ensure_minimum_width(the_matrix, target_width, fill_value):
    """ensure_minimum_width
    Ensure all rows in the given list of lists are at least as
    long as the given target_width value.
    Newly introduced values are assigned the fill_value value.
    """
    for vec in the_matrix:
        extend_list(vec, target_width, fill_value)


def convert_2d_table_py2c(x1_values, x2_values, y_values):
    x1_values_len = len(x1_values)
    x2_values_len = len(x2_values)
    y_values_len = sum([len(row) for row in y_values])
    assert (y_values_len == x1_values_len * x2_values_len)
    total_values = x1_values_len + x2_values_len + y_values_len
    c_all_values = (c_double * total_values)()

    offset = 0
    # copy x1 values
    for x1 in range(x1_values_len):
        c_all_values[offset + x1] = x1_values[x1]
    offset += x1_values_len

    # copy x2 values
    for x2 in range(x2_values_len):
        c_all_values[offset + x2] = x2_values[x2]
    offset += x2_values_len

    # copy y values
    for x2 in range(0, x2_values_len):
        for x1 in range(0, x1_values_len):
            c_all_values[offset] = y_values[x2][x1]
            offset += 1

    return c_all_values


def extract_2d_table_c2py(c_values):
    x1_axis_begin = 0
    x1_axis_len = c_values.data_lengths[0]
    x1_axis_end = x1_axis_begin + x1_axis_len

    x2_axis_begin = x1_axis_end
    x2_axis_len = c_values.data_lengths[1]
    x2_axis_end = x2_axis_begin + x2_axis_len

    table2d_begin = x2_axis_end
    table2d_len = x1_axis_len * x2_axis_len
    table2d_end = table2d_begin + table2d_len

    x1_axis = convert_list_c2py(c_values.data[x1_axis_begin:x1_axis_end], x1_axis_len)
    x2_axis = convert_list_c2py(c_values.data[x2_axis_begin:x2_axis_end], x2_axis_len)
    table2d = convert_matrix_c2py(c_values.data[table2d_begin:table2d_end], x1_axis_len, x2_axis_len)
    return x1_axis, x2_axis, table2d


def convert_m1d_table_py2c(x1_values, x2_values, y_values):
    nb_slices = len(x1_values)

    x1_values_len = len(x1_values)
    x2_values_len = len(x2_values)
    y_values_len = len(y_values)
    assert (x1_values_len == nb_slices)
    assert (x2_values_len == nb_slices)
    assert (y_values_len == nb_slices)

    x1_lengths = [len(slice) for slice in x1_values]
    y_lengths = [len(slice) for slice in y_values]
    assert (x1_lengths == y_lengths)
    x1_total_values = sum(x1_lengths)
    y_total_values = sum(x1_lengths)
    assert (x1_total_values == y_total_values)

    total_values = nb_slices + x1_total_values + y_total_values
    c_all_values = (c_double * total_values)()

    offset = 0
    # copy x2 values
    for x2 in range(x2_values_len):
        c_all_values[offset + x2] = x2_values[x2]
    offset += x2_values_len

    # copy x1 values
    for slice in range(nb_slices):
        slice_length = x1_lengths[slice]
        for val in range(slice_length):
            c_all_values[offset + val] = x1_values[slice][val]
        offset += slice_length

    # copy y values
    for slice in range(nb_slices):
        slice_length = y_lengths[slice]
        for val in range(slice_length):
            c_all_values[offset + val] = y_values[slice][val]
        offset += slice_length

    return c_all_values


def extract_m1d_table_c2py(c_values):
    nb_slices = c_values.data_lengths[0]
    slices_lengths = c_values.data_lengths[1:nb_slices + 1]

    x2_values_begin = 0
    x2_values_len = nb_slices
    x2_values_end = x2_values_begin + x2_values_len
    x2_values = convert_list_c2py(c_values.data[x2_values_begin:x2_values_end], x2_values_len)

    x1_values = []
    offset = x2_values_end
    for slice_length in slices_lengths:
        x1_values_begin = offset
        x1_values_len = slice_length
        x1_values_end = x1_values_begin + x1_values_len
        offset = x1_values_end

        x1_values.append(convert_list_c2py(c_values.data[x1_values_begin:x1_values_end], x1_values_len))

    y_values = []
    for slice_length in slices_lengths:
        y_values_begin = offset
        y_values_len = slice_length
        y_values_end = y_values_begin + y_values_len
        offset = y_values_end

        y_values.append(convert_list_c2py(c_values.data[y_values_begin:y_values_end], y_values_len))

    return x2_values, x1_values, y_values


def validate_params(func_name, valid_params, actual_params):
    invalid_keys = []
    for k, v in actual_params.items():
        if k not in valid_params and k != 'function':
            invalid_keys.append("'{}'".format(k))
    if invalid_keys:
        from amesim import AMESimError
        import os
        valid_keys = valid_params
        valid_keys.sort()
        valid_keys = ["'{}'".format(elem) for elem in valid_keys]
        valid_keys.insert(0, '')
        raise AMESimError(func_name,
                          "Function '{}' received unknown option(s): {}.\n"
                          "Supported keywords are: {}".format(func_name,
                                                              ', '.join(invalid_keys),
                                                              os.linesep.join(valid_keys)))
