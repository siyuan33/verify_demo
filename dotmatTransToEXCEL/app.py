import scipy.io
import pandas as pd
import os
import numpy as np

def convert_mat_to_excel(mat_file, output_dir):
    # 读取MAT文件
    mat_data = scipy.io.loadmat(mat_file)
    
    # 获取文件名，不包含扩展名
    file_name = os.path.splitext(os.path.basename(mat_file))[0]
    
    # 创建一个新的Excel文件名
    excel_file = os.path.join(output_dir, file_name + '.xlsx')
    
    # 创建一个Pandas Excel writer
    writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')
    
    for var_name in mat_data:
        if not var_name.startswith('__'):  # 忽略MAT文件中的私有变量
            data = mat_data[var_name]
            # 检查数据是否为二维数组（可以转换为DataFrame）
            if isinstance(data, (list, np.ndarray)) and data.ndim == 2:
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=var_name, index=False)
    
    # 保存Excel文件
    writer._save()

    print(f"Converted {mat_file} to {excel_file}")

def convert_all_mat_files_to_excel(root_dir):
    # 创建输出目录
    output_dir = os.path.join(root_dir, 'excel')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 遍历根目录下所有的.mat文件
    for file_name in os.listdir(root_dir):
        if file_name.endswith('.mat'):
            mat_file = os.path.join(root_dir, file_name)
            convert_mat_to_excel(mat_file, output_dir)

# 示例调用，假设根目录为当前目录
root_dir = '.'
convert_all_mat_files_to_excel(root_dir)
