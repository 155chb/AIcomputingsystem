import numpy as np
import struct
import os
import time

def show_matrix(mat, name):
    #print(name + str(mat.shape) + ' mean %f, std %f' % (mat.mean(), mat.std()))
    pass

def show_time(time, name):
    #print(name + str(time))
    pass

class ConvolutionalLayer(object):
    def __init__(self, kernel_size, channel_in, channel_out, padding, stride, type=1):
        self.kernel_size = kernel_size
        self.channel_in = channel_in
        self.channel_out = channel_out
        self.padding = padding
        self.stride = stride
        self.forward = self.forward_raw
        self.backward = self.backward_raw
        if type == 1:  # type 设为 1 时，使用优化后的 foward 和 backward 函数
            self.forward = self.forward_speedup
            self.backward = self.backward_speedup
        print('\tConvolutional layer with kernel size %d, input channel %d, output channel %d.' % (self.kernel_size, self.channel_in, self.channel_out))
    def init_param(self, std=0.01):
        self.weight = np.random.normal(loc=0.0, scale=std, size=(self.channel_in, self.kernel_size, self.kernel_size, self.channel_out))
        self.bias = np.zeros([self.channel_out])
        show_matrix(self.weight, 'conv weight ')
        show_matrix(self.bias, 'conv bias ')
    def forward_raw(self, input):
        start_time = time.time()
        self.input = input # [N, C, H, W]
        height = self.input.shape[2] + self.padding * 2
        width = self.input.shape[3] + self.padding * 2
        self.input_pad = np.zeros([self.input.shape[0], self.input.shape[1], height, width])
        self.input_pad[:, :, self.padding:self.padding+self.input.shape[2], self.padding:self.padding+self.input.shape[3]] = self.input
        height_out = (height - self.kernel_size) // self.stride + 1
        width_out = (width - self.kernel_size) // self.stride + 1
        self.output = np.zeros([self.input.shape[0], self.channel_out, height_out, width_out])
        for idxn in range(self.input.shape[0]):
            for idxc in range(self.channel_out):
                for idxh in range(height_out):
                    for idxw in range(width_out):
                        # TODO: 计算卷积层的前向传播，特征图与卷积核的内积再加偏置
                        self.output[idxn, idxc, idxh, idxw] = np.sum(self.input_pad[idxn, :, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size] * self.weight[:, :, :, idxc]) + self.bias[idxc]
        self.forward_time = time.time() - start_time
        return self.output
    def forward_speedup(self, input):
        # TODO: 改进forward函数，使得计算加速
        start_time = time.time()
        self.input = input
        height = self.input.shape[2] + self.padding * 2
        width = self.input.shape[3] + self.padding * 2
        self.input_pad = np.zeros([self.input.shape[0], self.input.shape[1], height, width])
        self.input_pad[:, :, self.padding:self.padding+self.input.shape[2], self.padding:self.padding+self.input.shape[3]] = self.input
        self.height_out = (height - self.kernel_size) // self.stride + 1
        self.width_out = (width - self.kernel_size) // self.stride + 1
        self.weight_reshape = np.reshape(self.weight, [-1, self.channel_out])
        self.img2col = np.zeros([self.input.shape[0] * self.height_out * self.width_out, self.channel_in * self.kernel_size * self.kernel_size])
        for idxn in range(self.input.shape[0]):
            for idxh in range(self.height_out):
                for idxw in range(self.width_out):
                    self.img2col[idxn*self.height_out*self.width_out+idxh*self.width_out+idxw, :] = self.input_pad[idxn, :, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size].flatten()
        self.output = np.matmul(self.img2col, self.weight_reshape) + self.bias
        self.output = np.reshape(self.output, [self.input.shape[0], self.height_out, self.width_out, self.channel_out])
        self.output = np.transpose(self.output, [0, 3, 1, 2])
        self.forward_time = time.time() - start_time
        return self.output
    def backward_speedup(self, top_diff):
        start_time = time.time()
        top_diff = np.transpose(top_diff, [0, 2, 3, 1])
        top_diff_reshape = np.reshape(top_diff, [top_diff.shape[0] * top_diff.shape[1] * top_diff.shape[2], top_diff.shape[3]])
        self.d_weight_reshape = np.matmul(self.img2col.T, top_diff_reshape)
        self.d_bias = np.sum(top_diff, axis=(0, 2, 3))
        bottom_diff_reshape = np.matmul(top_diff_reshape, self.weight_reshape.T)
        bottom_diff = np.zeros([self.input.shape[0], self.input.shape[1], self.input_pad.shape[2], self.input_pad.shape[3]])
        for idxn in range(self.input.shape[0]):
            for idxh in range(self.height_out):
                for idxw in range(self.width_out):
                    bottom_diff[idxn, :, idxh * self.stride:idxh * self.stride + self.kernel_size, idxw * self.stride:idxw * self.stride + self.kernel_size] += bottom_diff_reshape[idxn * self.height_out * self.width_out + idxh * self.width_out + idxw, :].reshape([self.channel_in, self.kernel_size, self.kernel_size])
        bottom_diff = bottom_diff[:, :, self.padding:self.padding + self.input.shape[2],
                      self.padding:self.padding + self.input.shape[3]]
        self.backward_time = time.time() - start_time
        return bottom_diff
    def backward_raw(self, top_diff):
        start_time = time.time()
        self.d_weight = np.zeros(self.weight.shape)
        self.d_bias = np.zeros(self.bias.shape)
        bottom_diff = np.zeros(self.input_pad.shape)
        for idxn in range(top_diff.shape[0]):
            for idxc in range(top_diff.shape[1]):
                for idxh in range(top_diff.shape[2]):
                    for idxw in range(top_diff.shape[3]):
                        # TODO： 计算卷积层的反向传播， 权重、偏置的梯度和本层损失
                        self.d_weight[:, :, :, idxc] += top_diff[idxn, idxc, idxh, idxw] * self.input_pad[idxn, :, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size]
                        self.d_bias[idxc] += top_diff[idxn, idxc, idxh, idxw]
                        bottom_diff[idxn, :, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size] += top_diff[idxn, idxc, idxh, idxw] * self.weight[:, :, :, idxc]
        bottom_diff = bottom_diff[:, :, self.padding:self.padding+self.input.shape[2], self.padding:self.padding+self.input.shape[3]]
        self.backward_time = time.time() - start_time
        return bottom_diff
    def get_gradient(self):
        return self.d_weight, self.d_bias
    def update_param(self, lr):
        self.weight += - lr * self.d_weight
        self.bias += - lr * self.d_bias
    def load_param(self, weight, bias):
        assert self.weight.shape == weight.shape
        assert self.bias.shape == bias.shape
        self.weight = weight
        self.bias = bias
        show_matrix(self.weight, 'conv weight ')
        show_matrix(self.bias, 'conv bias ')
    def get_forward_time(self):
        return self.forward_time
    def get_backward_time(self):
        return self.backward_time

class MaxPoolingLayer(object):
    def __init__(self, kernel_size, stride, type=1):
        self.kernel_size = kernel_size
        self.stride = stride
        ### adding
        self.forward = self.forward_raw
        self.backward = self.backward_raw_book
        if type == 1: # type 设为 1 时，使用优化后的 foward 和 backward 函数
            self.forward = self.forward_speedup
            self.backward = self.backward_speedup

        print('\tMax pooling layer with kernel size %d, stride %d.' % (self.kernel_size, self.stride))
    def forward_raw(self, input):
        start_time = time.time()
        self.input = input # [N, C, H, W]
        self.max_index = np.zeros(self.input.shape)
        height_out = (self.input.shape[2] - self.kernel_size) // self.stride + 1
        width_out = (self.input.shape[3] - self.kernel_size) // self.stride + 1
        self.output = np.zeros([self.input.shape[0], self.input.shape[1], height_out, width_out])
        for idxn in range(self.input.shape[0]):
            for idxc in range(self.input.shape[1]):
                for idxh in range(height_out):
                    for idxw in range(width_out):
                        # TODO： 计算最大池化层的前向传播， 取池化窗口内的最大值
                        self.output[idxn, idxc, idxh, idxw] = np.max(self.input[idxn, idxc, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size])
                        curren_max_index = np.argmax(self.input[idxn, idxc, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size])
                        curren_max_index = np.unravel_index(curren_max_index, [self.kernel_size, self.kernel_size])
                        self.max_index[idxn, idxc, idxh*self.stride+curren_max_index[0], idxw*self.stride+curren_max_index[1]] = 1
        self.forward_time = time.time() - start_time
        return self.output
    def forward_speedup(self, input):
        # TODO: 改进forward函数，使得计算加速
        start_time = time.time()
        self.input = input
        height_out = (self.input.shape[2] - self.kernel_size) // self.stride + 1
        width_out = (self.input.shape[3] - self.kernel_size) // self.stride + 1
        self.output = np.zeros([self.input.shape[0], self.input.shape[1], height_out, width_out])
        self.img2col = np.zeros([self.input.shape[0] * height_out * width_out, self.input.shape[1] * self.kernel_size * self.kernel_size])
        self.max_index = np.zeros(self.img2col.shape)
        self.max_index = np.reshape(self.max_index, [self.input.shape[0] * height_out * width_out * self.input.shape[1], self.kernel_size * self.kernel_size])
        for idxn in range(self.input.shape[0]):
            for idxh in range(height_out):
                for idxw in range(width_out):
                    self.img2col[idxn*height_out*width_out+idxh*width_out+idxw, :] = self.input[idxn, :, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size].flatten()
        self.img2col = np.reshape(self.img2col, [self.input.shape[0] * height_out * width_out * self.input.shape[1], self.kernel_size * self.kernel_size])
        max_index = np.argmax(self.img2col, axis=1)
        self.max_index[np.arange(self.input.shape[0] * height_out * width_out * self.input.shape[1]), max_index] = 1
        self.img2col = np.reshape(self.img2col, [self.input.shape[0], height_out, width_out, self.input.shape[1], self.kernel_size * self.kernel_size])
        self.output = np.max(self.img2col, axis=4)
        self.output = np.transpose(self.output, [0, 3, 1, 2])
        self.forward_time = time.time() - start_time
        return self.output
    def backward_speedup(self, top_diff):
        # TODO: 改进backward函数，使得计算加速
        start_time = time.time()
        top_diff = np.transpose(top_diff, [0, 2, 3, 1])
        bottom_diff_reshape = top_diff.reshape([-1, 1]) * self.max_index
        bottom_diff_reshape = bottom_diff_reshape.reshape([top_diff.shape[0], top_diff.shape[1], top_diff.shape[2], top_diff.shape[3], self.kernel_size, self.kernel_size])
        bottom_diff = np.zeros(self.input.shape)
        for idxn in range(self.input.shape[0]):
            for idxh in range(self.input.shape[2] // self.stride):
                for idxw in range(self.input.shape[3] // self.stride):
                    bottom_diff[idxn, :, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size] += bottom_diff_reshape[idxn, idxh, idxw]
        self.backward_time = time.time() - start_time
        return bottom_diff
    def backward_raw_book(self, top_diff):
        start_time = time.time()
        bottom_diff = np.zeros(self.input.shape)
        for idxn in range(top_diff.shape[0]):
            for idxc in range(top_diff.shape[1]):
                for idxh in range(top_diff.shape[2] // self.stride):
                    for idxw in range(top_diff.shape[3] // self.stride):
                        max_index = np.argmax(self.input[idxn, idxc, idxh*self.stride:idxh*self.stride+self.kernel_size, idxw*self.stride:idxw*self.stride+self.kernel_size])
                        max_index = np.unravel_index(max_index, [self.kernel_size, self.kernel_size])
                        bottom_diff[idxn, idxc, idxh*self.stride+max_index[0], idxw*self.stride+max_index[1]] = top_diff[idxn, idxc, idxh, idxw]
        show_matrix(top_diff, 'top_diff--------')
        show_matrix(bottom_diff, 'max pooling d_h ')
        self.backward_time = time.time() - start_time
        return bottom_diff

class FlattenLayer(object):
    def __init__(self, input_shape, output_shape):
        self.input_shape = input_shape
        self.output_shape = output_shape
        assert np.prod(self.input_shape) == np.prod(self.output_shape)
        print('\tFlatten layer with input shape %s, output shape %s.' % (str(self.input_shape), str(self.output_shape)))
    def forward(self, input):
        try:
            assert list(input.shape[1:]) == list(self.input_shape)
        except Exception as e:
            print("input.shape", input.shape)
            print("input.shape[1:]", input.shape[1:])
            print("self.input_shape", self.input_shape)
            assert list(input.shape[1:]) == list(self.input_shape)
        # matconvnet feature map dim: [N, height, width, channel]
        # ours feature map dim: [N, channel, height, width]
        self.input = np.transpose(input, [0, 2, 3, 1])
        self.output = self.input.reshape([self.input.shape[0]] + list(self.output_shape))
        show_matrix(self.output, 'flatten out ')
        return self.output
    def backward(self, top_diff):
        try:
            assert list(top_diff.shape[1:]) == list(self.output_shape)
        except Exception as e:
            print("top_diff.shape", top_diff.shape)
            print("top_diff.shape[1:]", top_diff.shape[1:])
            print("self.output_shape", self.output_shape)
            assert list(top_diff.shape[1:]) == list(self.output_shape)
        top_diff = np.transpose(top_diff, [0, 3, 1, 2])
        bottom_diff = top_diff.reshape([top_diff.shape[0]] + list(self.input_shape))
        show_matrix(bottom_diff, 'flatten d_h ')
        return bottom_diff
