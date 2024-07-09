import scipy.io
import pandas as pd

# 读取MAT文件
mat = scipy.io.loadmat('./test.mat')

# 打印文件中的变量名
print(mat.keys())

# 假设你要提取变量 'data' 并将其转换为DataFrame
data = mat['data']

# 将数据转换为DataFrame
df = pd.DataFrame(data)

# 将DataFrame保存为CSV文件
df.to_csv('output_file.csv', index=False)
