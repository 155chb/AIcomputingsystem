import numpy as np


def elementwise_multiply(V, A):
    # 将向量 V 视为形状为 (k, 1) 的列向量
    V_column = V[:, np.newaxis]

    # 将其与矩阵 A 相乘
    M = V_column * A

    return M


# 示例：向量 V 长度为 k，矩阵 A 形状为 k*m
V = np.array([1, 2, 3])
A = np.array([[1, 2, 3],
              [4, 5, 6],
              [7, 8, 9]])

M = elementwise_multiply(V, A)
print(M)
