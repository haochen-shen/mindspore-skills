"""Convert PyTorch Python sources to MindSpore via libcst transforms."""

import argparse
import os
import re
import shutil
from typing import Set, Tuple

import libcst as cst
import libcst.matchers as m
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider

USAGE = """Usage:
  Folder conversion (ALL Python files):
    python auto_convert.py --src_root /path/to/src --dst_root /path/to/dst

  Selective file conversion (RECOMMENDED):
    python auto_convert.py --src_root /path/to/src --dst_root /path/to/dst \\
        --files "models/controlnet.py" "pipelines/flux/*.py"

  Single-file in-place conversion:
    python auto_convert.py --src_file /path/to/file.py --inplace
"""

mint_map = {
    "torch.arange": "mindspore.mint.arange",
    "torch.ge": "mindspore.mint.ge",
    "torch.bernoulli": "mindspore.mint.bernoulli",
    "torch.isnan": "mindspore.mint.isnan",
    "torch.bincount": "mindspore.mint.bincount",
    "torch.clone": "mindspore.mint.clone",
    "torch.eye": "mindspore.mint.eye",
    "torch.einsum": "mindspore.mint.einsum",
    "torch.empty": "mindspore.mint.empty",
    "torch.empty_like": "mindspore.mint.empty_like",
    "torch.full_like": "mindspore.mint.full_like",
    "torch.linspace": "mindspore.mint.linspace",
    "torch.ones": "mindspore.mint.ones",
    "torch.ones_like": "mindspore.mint.ones_like",
    "torch.randint": "mindspore.mint.randint",
    "torch.randint_like": "mindspore.mint.randint_like",
    "torch.randn": "mindspore.mint.randn",
    "torch.randn_like": "mindspore.mint.randn_like",
    "torch.randperm": "mindspore.mint.randperm",
    "torch.zeros": "mindspore.mint.zeros",
    "torch.zeros_like": "mindspore.mint.zeros_like",
    "torch.cat": "mindspore.mint.cat",
    "torch.chunk": "mindspore.mint.chunk",
    "torch.concat": "mindspore.mint.concat",
    "torch.count_nonzero": "mindspore.mint.count_nonzero",
    "torch.gather": "mindspore.mint.gather",
    "torch.index_add": "mindspore.mint.index_add",
    "torch.index_select": "mindspore.mint.index_select",
    "torch.masked_select": "mindspore.mint.masked_select",
    "torch.permute": "mindspore.mint.permute",
    "torch.reshape": "mindspore.mint.reshape",
    "torch.scatter": "mindspore.mint.scatter",
    "torch.scatter_add": "mindspore.mint.scatter_add",
    "torch.split": "mindspore.mint.split",
    "torch.narrow": "mindspore.mint.narrow",
    "torch.nonzero": "mindspore.mint.nonzero",
    "torch.tile": "mindspore.mint.tile",
    "torch.tril": "mindspore.mint.tril",
    "torch.select": "mindspore.mint.select",
    "torch.squeeze": "mindspore.mint.squeeze",
    "torch.stack": "mindspore.mint.stack",
    "torch.swapaxes": "mindspore.mint.swapaxes",
    "torch.transpose": "mindspore.mint.transpose",
    "torch.triu": "mindspore.mint.triu",
    "torch.unbind": "mindspore.mint.unbind",
    "torch.unique_consecutive": "mindspore.mint.unique_consecutive",
    "torch.unsqueeze": "mindspore.mint.unsqueeze",
    "torch.where": "mindspore.mint.where",
    "torch.multinomial": "mindspore.mint.multinomial",
    "torch.normal": "mindspore.mint.normal",
    "torch.rand_like": "mindspore.mint.rand_like",
    "torch.rand": "mindspore.mint.rand",
    "torch.abs": "mindspore.mint.abs",
    "torch.add": "mindspore.mint.add",
    "torch.addmv": "mindspore.mint.addmv",
    "torch.acos": "mindspore.mint.acos",
    "torch.acosh": "mindspore.mint.acosh",
    "torch.arccos": "mindspore.mint.arccos",
    "torch.arccosh": "mindspore.mint.arccosh",
    "torch.arcsin": "mindspore.mint.arcsin",
    "torch.arcsinh": "mindspore.mint.arcsinh",
    "torch.arctan": "mindspore.mint.arctan",
    "torch.arctan2": "mindspore.mint.arctan2",
    "torch.arctanh": "mindspore.mint.arctanh",
    "torch.asin": "mindspore.mint.asin",
    "torch.asinh": "mindspore.mint.asinh",
    "torch.atan": "mindspore.mint.atan",
    "torch.atan2": "mindspore.mint.atan2",
    "torch.atanh": "mindspore.mint.atanh",
    "torch.bitwise_and": "mindspore.mint.bitwise_and",
    "torch.bitwise_or": "mindspore.mint.bitwise_or",
    "torch.bitwise_xor": "mindspore.mint.bitwise_xor",
    "torch.ceil": "mindspore.mint.ceil",
    "torch.clamp": "mindspore.mint.clamp",
    "torch.cos": "mindspore.mint.cos",
    "torch.cosh": "mindspore.mint.cosh",
    "torch.cross": "mindspore.mint.cross",
    "torch.diff": "mindspore.mint.diff",
    "torch.div": "mindspore.mint.div",
    "torch.divide": "mindspore.mint.divide",
    "torch.erf": "mindspore.mint.erf",
    "torch.erfc": "mindspore.mint.erfc",
    "torch.erfinv": "mindspore.mint.erfinv",
    "torch.exp": "mindspore.mint.exp",
    "torch.exp2": "mindspore.mint.exp2",
    "torch.expm1": "mindspore.mint.expm1",
    "torch.fix": "mindspore.mint.fix",
    "torch.float_power": "mindspore.mint.float_power",
    "torch.floor": "mindspore.mint.floor",
    "torch.fmod": "mindspore.mint.fmod",
    "torch.frac": "mindspore.mint.frac",
    "torch.lerp": "mindspore.mint.lerp",
    "torch.log": "mindspore.mint.log",
    "torch.log1p": "mindspore.mint.log1p",
    "torch.log2": "mindspore.mint.log2",
    "torch.log10": "mindspore.mint.log10",
    "torch.logaddexp": "mindspore.mint.logaddexp",
    "torch.logaddexp2": "mindspore.mint.logaddexp2",
    "torch.logical_and": "mindspore.mint.logical_and",
    "torch.logical_not": "mindspore.mint.logical_not",
    "torch.logical_or": "mindspore.mint.logical_or",
    "torch.logical_xor": "mindspore.mint.logical_xor",
    "torch.mul": "mindspore.mint.mul",
    "torch.mv": "mindspore.mint.mv",
    "torch.nansum": "mindspore.mint.nansum",
    "torch.nan_to_num": "mindspore.mint.nan_to_num",
    "torch.neg": "mindspore.mint.neg",
    "torch.negative": "mindspore.mint.negative",
    "torch.pow": "mindspore.mint.pow",
    "torch.polar": "mindspore.mint.polar",
    "torch.ravel": "mindspore.mint.ravel",
    "torch.reciprocal": "mindspore.mint.reciprocal",
    "torch.remainder": "mindspore.mint.remainder",
    "torch.roll": "mindspore.mint.roll",
    "torch.round": "mindspore.mint.round",
    "torch.rsqrt": "mindspore.mint.rsqrt",
    "torch.sigmoid": "mindspore.mint.sigmoid",
    "torch.sign": "mindspore.mint.sign",
    "torch.sin": "mindspore.mint.sin",
    "torch.sinc": "mindspore.mint.sinc",
    "torch.sinh": "mindspore.mint.sinh",
    "torch.softmax": "mindspore.mint.softmax",
    "torch.sqrt": "mindspore.mint.sqrt",
    "torch.square": "mindspore.mint.square",
    "torch.sub": "mindspore.mint.sub",
    "torch.t": "mindspore.mint.t",
    "torch.tan": "mindspore.mint.tan",
    "torch.tanh": "mindspore.mint.tanh",
    "torch.trunc": "mindspore.mint.trunc",
    "torch.xlogy": "mindspore.mint.xlogy",
    "torch.amax": "mindspore.mint.amax",
    "torch.amin": "mindspore.mint.amin",
    "torch.argmax": "mindspore.mint.argmax",
    "torch.argmin": "mindspore.mint.argmin",
    "torch.argsort": "mindspore.mint.argsort",
    "torch.all": "mindspore.mint.all",
    "torch.any": "mindspore.mint.any",
    "torch.cumprod": "mindspore.mint.cumprod",
    "torch.histc": "mindspore.mint.histc",
    "torch.logsumexp": "mindspore.mint.logsumexp",
    "torch.max": "mindspore.mint.max",
    "torch.mean": "mindspore.mint.mean",
    "torch.median": "mindspore.mint.median",
    "torch.min": "mindspore.mint.min",
    "torch.norm": "mindspore.mint.norm",
    "torch.prod": "mindspore.mint.prod",
    "torch.sum": "mindspore.mint.sum",
    "torch.std": "mindspore.mint.std",
    "torch.std_mean": "mindspore.mint.std_mean",
    "torch.unique": "mindspore.mint.unique",
    "torch.var": "mindspore.mint.var",
    "torch.var_mean": "mindspore.mint.var_mean",
    "torch.allclose": "mindspore.mint.allclose",
    "torch.argsort": "mindspore.mint.argsort",
    "torch.eq": "mindspore.mint.eq",
    "torch.equal": "mindspore.mint.equal",
    "torch.greater": "mindspore.mint.greater",
    "torch.greater_equal": "mindspore.mint.greater_equal",
    "torch.gt": "mindspore.mint.gt",
    "torch.isclose": "mindspore.mint.isclose",
    "torch.isfinite": "mindspore.mint.isfinite",
    "torch.isinf": "mindspore.mint.isinf",
    "torch.isneginf": "mindspore.mint.isneginf",
    "torch.le": "mindspore.mint.le",
    "torch.less": "mindspore.mint.less",
    "torch.less_equal": "mindspore.mint.less_equal",
    "torch.lt": "mindspore.mint.lt",
    "torch.maximum": "mindspore.mint.maximum",
    "torch.minimum": "mindspore.mint.minimum",
    "torch.ne": "mindspore.mint.ne",
    "torch.not_equal": "mindspore.mint.not_equal",
    "torch.topk": "mindspore.mint.topk",
    "torch.sort": "mindspore.mint.sort",
    "torch.addbmm": "mindspore.mint.addbmm",
    "torch.addmm": "mindspore.mint.addmm",
    "torch.baddbmm": "mindspore.mint.baddbmm",
    "torch.bmm": "mindspore.mint.bmm",
    "torch.dot": "mindspore.mint.dot",
    "torch.inverse": "mindspore.mint.inverse",
    "torch.matmul": "mindspore.mint.matmul",
    "torch.meshgrid": "mindspore.mint.meshgrid",
    "torch.mm": "mindspore.mint.mm",
    "torch.outer": "mindspore.mint.outer",
    "torch.trace": "mindspore.mint.trace",
    "torch.broadcast_to": "mindspore.mint.broadcast_to",
    "torch.cdist": "mindspore.mint.cdist",
    "torch.cummax": "mindspore.mint.cummax",
    "torch.cummin": "mindspore.mint.cummin",
    "torch.cumsum": "mindspore.mint.cumsum",
    "torch.diag": "mindspore.mint.diag",
    "torch.flatten": "mindspore.mint.flatten",
    "torch.flip": "mindspore.mint.flip",
    "torch.repeat_interleave": "mindspore.mint.repeat_interleave",
    "torch.searchsorted": "mindspore.mint.searchsorted",
    "torch.tril": "mindspore.mint.tril",
    "torch.triangular_solve": "mindspore.mint.triangular_solve",
    "torch.clip": "mindspore.mint.clamp",
    "torch.concatenate": "mindspore.mint.cat",
    "torch.log_softmax": "mindspore.mint.nn.functional.log_softmax",
}

mint_nn_map = {
    "torch.nn.Conv2d": "mindspore.mint.nn.Conv2d",
    "torch.nn.Conv3d": "mindspore.mint.nn.Conv3d",
    "torch.nn.ConvTranspose2d": "mindspore.mint.nn.ConvTranspose2d",
    "torch.nn.Fold": "mindspore.mint.nn.Fold",
    "torch.nn.Unfold": "mindspore.mint.nn.Unfold",
    "torch.nn.BatchNorm1d": "mindspore.mint.nn.BatchNorm1d",
    "torch.nn.BatchNorm2d": "mindspore.mint.nn.BatchNorm2d",
    "torch.nn.BatchNorm3d": "mindspore.mint.nn.BatchNorm3d",
    "torch.nn.GroupNorm": "mindspore.mint.nn.GroupNorm",
    "torch.nn.LayerNorm": "mindspore.mint.nn.LayerNorm",
    "torch.nn.SyncBatchNorm": "mindspore.mint.nn.SyncBatchNorm",
    "torch.nn.ELU": "mindspore.mint.nn.ELU",
    "torch.nn.GELU": "mindspore.mint.nn.GELU",
    "torch.nn.GLU": "mindspore.mint.nn.GLU",
    "torch.nn.Hardshrink": "mindspore.mint.nn.Hardshrink",
    "torch.nn.Hardsigmoid": "mindspore.mint.nn.Hardsigmoid",
    "torch.nn.Hardswish": "mindspore.mint.nn.Hardswish",
    "torch.nn.LogSigmoid": "mindspore.mint.nn.LogSigmoid",
    "torch.nn.LogSoftmax": "mindspore.mint.nn.LogSoftmax",
    "torch.nn.Mish": "mindspore.mint.nn.Mish",
    "torch.nn.PReLU": "mindspore.mint.nn.PReLU",
    "torch.nn.ReLU": "mindspore.mint.nn.ReLU",
    "torch.nn.ReLU6": "mindspore.mint.nn.ReLU6",
    "torch.nn.SELU": "mindspore.mint.nn.SELU",
    "torch.nn.SiLU": "mindspore.mint.nn.SiLU",
    "torch.nn.Sigmoid": "mindspore.mint.nn.Sigmoid",
    "torch.nn.Softmax": "mindspore.mint.nn.Softmax",
    "torch.nn.Softshrink": "mindspore.mint.nn.Softshrink",
    "torch.nn.Tanh": "mindspore.mint.nn.Tanh",
    "torch.nn.Embedding": "mindspore.mint.nn.Embedding",
    "torch.nn.Linear": "mindspore.mint.nn.Linear",
    "torch.nn.Dropout": "mindspore.mint.nn.Dropout",
    "torch.nn.Dropout2d": "mindspore.mint.nn.Dropout2d",
    "torch.nn.AdaptiveAvgPool1d": "mindspore.mint.nn.AdaptiveAvgPool1d",
    "torch.nn.AdaptiveAvgPool2d": "mindspore.mint.nn.AdaptiveAvgPool2d",
    "torch.nn.AdaptiveAvgPool3d": "mindspore.mint.nn.AdaptiveAvgPool3d",
    "torch.nn.AdaptiveMaxPool1d": "mindspore.mint.nn.AdaptiveMaxPool1d",
    "torch.nn.AvgPool2d": "mindspore.mint.nn.AvgPool2d",
    "torch.nn.AvgPool3d": "mindspore.mint.nn.AvgPool3d",
    "torch.nn.MaxUnpool2d": "mindspore.mint.nn.MaxUnpool2d",
    "torch.nn.ConstantPad1d": "mindspore.mint.nn.ConstantPad1d",
    "torch.nn.ConstantPad2d": "mindspore.mint.nn.ConstantPad2d",
    "torch.nn.ConstantPad3d": "mindspore.mint.nn.ConstantPad3d",
    "torch.nn.ReflectionPad1d": "mindspore.mint.nn.ReflectionPad1d",
    "torch.nn.ReflectionPad2d": "mindspore.mint.nn.ReflectionPad2d",
    "torch.nn.ReflectionPad3d": "mindspore.mint.nn.ReflectionPad3d",
    "torch.nn.ReplicationPad1d": "mindspore.mint.nn.ReplicationPad1d",
    "torch.nn.ReplicationPad2d": "mindspore.mint.nn.ReplicationPad2d",
    "torch.nn.ReplicationPad3d": "mindspore.mint.nn.ReplicationPad3d",
    "torch.nn.ZeroPad1d": "mindspore.mint.nn.ZeroPad1d",
    "torch.nn.ZeroPad2d": "mindspore.mint.nn.ZeroPad2d",
    "torch.nn.ZeroPad3d": "mindspore.mint.nn.ZeroPad3d",
    "torch.nn.BCELoss": "mindspore.mint.nn.BCELoss",
    "torch.nn.BCEWithLogitsLoss": "mindspore.mint.nn.BCEWithLogitsLoss",
    "torch.nn.CrossEntropyLoss": "mindspore.mint.nn.CrossEntropyLoss",
    "torch.nn.KLDivLoss": "mindspore.mint.nn.KLDivLoss",
    "torch.nn.L1Loss": "mindspore.mint.nn.L1Loss",
    "torch.nn.MSELoss": "mindspore.mint.nn.MSELoss",
    "torch.nn.NLLLoss": "mindspore.mint.nn.NLLLoss",
    "torch.nn.SmoothL1Loss": "mindspore.mint.nn.SmoothL1Loss",
    "torch.nn.PixelShuffle": "mindspore.mint.nn.PixelShuffle",
    "torch.nn.Upsample": "mindspore.mint.nn.Upsample",
    "torch.nn.Identity": "mindspore.mint.nn.Identity",
    "torch.nn.functional.conv2d": "mindspore.mint.nn.functional.conv2d",
    "torch.nn.functional.conv3d": "mindspore.mint.nn.functional.conv3d",
    "torch.nn.functional.conv_transpose2d": "mindspore.mint.nn.functional.conv_transpose2d",
    "torch.nn.functional.fold": "mindspore.mint.nn.functional.fold",
    "torch.nn.functional.unfold": "mindspore.mint.nn.functional.unfold",
    "torch.nn.functional.adaptive_avg_pool1d": "mindspore.mint.nn.functional.adaptive_avg_pool1d",
    "torch.nn.functional.adaptive_avg_pool2d": "mindspore.mint.nn.functional.adaptive_avg_pool2d",
    "torch.nn.functional.adaptive_avg_pool3d": "mindspore.mint.nn.functional.adaptive_avg_pool3d",
    "torch.nn.functional.adaptive_max_pool1d": "mindspore.mint.nn.functional.adaptive_max_pool1d",
    "torch.nn.functional.avg_pool1d": "mindspore.mint.nn.functional.avg_pool1d",
    "torch.nn.functional.avg_pool2d": "mindspore.mint.nn.functional.avg_pool2d",
    "torch.nn.functional.avg_pool3d": "mindspore.mint.nn.functional.avg_pool3d",
    "torch.nn.functional.max_pool2d": "mindspore.mint.nn.functional.max_pool2d",
    "torch.nn.functional.max_unpool2d": "mindspore.mint.nn.functional.max_unpool2d",
    "torch.nn.functional.batch_norm": "mindspore.mint.nn.functional.batch_norm",
    "torch.nn.functional.elu": "mindspore.mint.nn.functional.elu",
    "torch.nn.functional.elu_": "mindspore.mint.nn.functional.elu_",
    "torch.nn.functional.gelu": "mindspore.mint.nn.functional.gelu",
    "torch.nn.functional.glu": "mindspore.mint.nn.functional.glu",
    "torch.nn.functional.group_norm": "mindspore.mint.nn.functional.group_norm",
    "torch.nn.functional.hardshrink": "mindspore.mint.nn.functional.hardshrink",
    "torch.nn.functional.hardsigmoid": "mindspore.mint.nn.functional.hardsigmoid",
    "torch.nn.functional.hardswish": "mindspore.mint.nn.functional.hardswish",
    "torch.nn.functional.layer_norm": "mindspore.mint.nn.functional.layer_norm",
    "torch.nn.functional.leaky_relu": "mindspore.mint.nn.functional.leaky_relu",
    "torch.nn.functional.log_softmax": "mindspore.mint.nn.functional.log_softmax",
    "torch.nn.functional.logsigmoid": "mindspore.mint.nn.functional.logsigmoid",
    "torch.nn.functional.mish": "mindspore.mint.nn.functional.mish",
    "torch.nn.functional.prelu": "mindspore.mint.nn.functional.prelu",
    "torch.nn.functional.relu": "mindspore.mint.nn.functional.relu",
    "torch.nn.functional.relu6": "mindspore.mint.nn.functional.relu6",
    "torch.nn.functional.relu_": "mindspore.mint.nn.functional.relu_",
    "torch.nn.functional.selu": "mindspore.mint.nn.functional.selu",
    "torch.nn.functional.sigmoid": "mindspore.mint.nn.functional.sigmoid",
    "torch.nn.functional.silu": "mindspore.mint.nn.functional.silu",
    "torch.nn.functional.softmax": "mindspore.mint.nn.functional.softmax",
    "torch.nn.functional.softplus": "mindspore.mint.nn.functional.softplus",
    "torch.nn.functional.softshrink": "mindspore.mint.nn.functional.softshrink",
    "torch.nn.functional.tanh": "mindspore.mint.nn.functional.tanh",
    "torch.nn.functional.normalize": "mindspore.mint.nn.functional.normalize",
    "torch.nn.functional.linear": "mindspore.mint.nn.functional.linear",
    "torch.nn.functional.dropout": "mindspore.mint.nn.functional.dropout",
    "torch.nn.functional.dropout2d": "mindspore.mint.nn.functional.dropout2d",
    "torch.nn.functional.embedding": "mindspore.mint.nn.functional.embedding",
    "torch.nn.functional.one_hot": "mindspore.mint.nn.functional.one_hot",
    "torch.nn.functional.cross_entropy": "mindspore.mint.nn.functional.cross_entropy",
    "torch.nn.functional.binary_cross_entropy": "mindspore.mint.nn.functional.binary_cross_entropy",
    "torch.nn.functional.binary_cross_entropy_with_logits": "mindspore.mint.nn.functional.binary_cross_entropy_with_logits",
    "torch.nn.functional.kl_div": "mindspore.mint.nn.functional.kl_div",
    "torch.nn.functional.l1_loss": "mindspore.mint.nn.functional.l1_loss",
    "torch.nn.functional.mse_loss": "mindspore.mint.nn.functional.mse_loss",
    "torch.nn.functional.nll_loss": "mindspore.mint.nn.functional.nll_loss",
    "torch.nn.functional.smooth_l1_loss": "mindspore.mint.nn.functional.smooth_l1_loss",
    "torch.nn.functional.interpolate": "mindspore.mint.nn.functional.interpolate",
    "torch.nn.functional.grid_sample": "mindspore.mint.nn.functional.grid_sample",
    "torch.nn.functional.pad": "mindspore.mint.nn.functional.pad",
    "torch.nn.functional.pixel_shuffle": "mindspore.mint.nn.functional.pixel_shuffle",
    "torch.nn.Module": "mindspore.nn.Cell",
    "torch.nn.Sequential": "mindspore.nn.SequentialCell",
    "torch.nn.ModuleList": "mindspore.nn.CellList",
    "torch.nn.ModuleDict": "mindspore.nn.CellDict",
    "torch.nn.Flatten": "mindspore.nn.Flatten",
    "torch.nn.CTCLoss": "mindspore.nn.CTCLoss",
}

ops_map = {
    "torch.addcmul": "mindspore.ops.addcmul",
    "torch.argwhere": "mindspore.ops.argwhere",
    "torch.bucketize": "mindspore.ops.bucketize",
    "torch.conj": "mindspore.ops.conj",
    "torch.cosine_similarity": "mindspore.ops.cosine_similarity",
    "torch.deg2rad": "mindspore.ops.deg2rad",
    "torch.hann_window": "mindspore.ops.hann_window",
    "torch.hstack": "mindspore.ops.hstack",
    "torch.masked_fill": "mindspore.ops.masked_fill",
    "torch.multiply": "mindspore.ops.multiply",
    "torch.numel": "mindspore.ops.numel",
    "torch.range": "mindspore.ops.range",
    "torch.relu": "mindspore.ops.relu",
    "torch.nn.functional.ctc_loss": "mindspore.ops.ctc_loss",
    "torch.nn.functional.gumbel_softmax": "mindspore.ops.gumbel_softmax",
    "torch.full": "mindspore.ops.full",
    "torch.fill": "mindspore.ops.fill",
}

# Diffusers-specific mappings (minimal)
diffusers_qwen_map = {
    "diffusers.QwenImagePipeline": "mindone.diffusers.pipelines.QwenImagePipeline",
    "diffusers.pipelines.qwenimage.QwenImagePipeline": "mindone.diffusers.pipelines.qwenimage.QwenImagePipeline",
    "diffusers.QwenImageEditPipeline": "mindone.diffusers.pipelines.QwenImageEditPipeline",
    "diffusers.pipelines.qwenimage.QwenImageEditPipeline": "mindone.diffusers.pipelines.qwenimage.QwenImageEditPipeline",
    "diffusers.QwenImageImg2ImgPipeline": "mindone.diffusers.pipelines.QwenImageImg2ImgPipeline",
    "diffusers.pipelines.qwenimage.QwenImageImg2ImgPipeline": "mindone.diffusers.pipelines.qwenimage.QwenImageImg2ImgPipeline",
    "diffusers.QwenImageInpaintPipeline": "mindone.diffusers.pipelines.QwenImageInpaintPipeline",
    "diffusers.pipelines.qwenimage.QwenImageInpaintPipeline": "mindone.diffusers.pipelines.qwenimage.QwenImageInpaintPipeline",
}

diffusers_qwen_scheduler_map = {
    "diffusers.schedulers.FlowMatchEulerDiscreteScheduler": "mindone.diffusers.schedulers.FlowMatchEulerDiscreteScheduler",
    "diffusers.FlowMatchEulerDiscreteScheduler": "mindone.diffusers.schedulers.FlowMatchEulerDiscreteScheduler",
}

diffusers_qwen_model_map = {
    "diffusers.models.AutoencoderKLQwenImage": "mindone.diffusers.models.AutoencoderKLQwenImage",
    "diffusers.AutoencoderKLQwenImage": "mindone.diffusers.models.AutoencoderKLQwenImage",
    "diffusers.models.QwenImageTransformer2DModel": "mindone.diffusers.models.QwenImageTransformer2DModel",
    "diffusers.QwenImageTransformer2DModel": "mindone.diffusers.models.QwenImageTransformer2DModel",
}

diffusers_qwen_loader_map = {
    "diffusers.loaders.QwenImageLoraLoaderMixin": "mindone.diffusers.loaders.QwenImageLoraLoaderMixin",
    "diffusers.QwenImageLoraLoaderMixin": "mindone.diffusers.loaders.QwenImageLoraLoaderMixin",
}

diffusers_utility_map = {
    "diffusers.utils.torch_utils.randn_tensor": "mindone.diffusers.utils.mindspore_utils.randn_tensor",
    "diffusers.utils.randn_tensor": "mindone.diffusers.utils.mindspore_utils.randn_tensor",
    "diffusers.utils.is_torch_xla_available": None,  # Remove - not used in mindone
}

diffusers_transformers_map = {
    "transformers.Qwen2_5_VLForConditionalGeneration": "mindone.diffusers.transformers.Qwen2_5_VLForConditionalGeneration",
    "transformers.Qwen2Tokenizer": "mindone.diffusers.transformers.Qwen2Tokenizer",
}

diffusers_unet_map = {
    "diffusers.models.unets.unet_2d_condition.UNet2DConditionModel": "mindone.diffusers.models.unets.UNet2DConditionModel",
    "diffusers.UNet2DConditionModel": "mindone.diffusers.models.unets.UNet2DConditionModel",
    "diffusers.models.unets.unet_2d.UNet2DModel": "mindone.diffusers.models.unets.UNet2DModel",
    "diffusers.UNet2DModel": "mindone.diffusers.models.unets.UNet2DModel",
}

diffusers_vae_map = {
    "diffusers.models.autoencoders.autoencoder_kl.AutoencoderKL": "mindone.diffusers.models.autoencoders.AutoencoderKL",
    "diffusers.AutoencoderKL": "mindone.diffusers.models.autoencoders.AutoencoderKL",
    "diffusers.models.autoencoders.vae.VAE": "mindone.diffusers.models.autoencoders.VAE",
    "diffusers.VAE": "mindone.diffusers.models.autoencoders.VAE",
}

diffusers_scheduler_map = {
    "diffusers.schedulers.scheduling_euler_discrete.EulerDiscreteScheduler": "mindone.diffusers.schedulers.EulerDiscreteScheduler",
    "diffusers.EulerDiscreteScheduler": "mindone.diffusers.schedulers.EulerDiscreteScheduler",
    "diffusers.schedulers.scheduling_ddpm.DDPMScheduler": "mindone.diffusers.schedulers.DDPMScheduler",
    "diffusers.DDPMScheduler": "mindone.diffusers.schedulers.DDPMScheduler",
    "diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler": "mindone.diffusers.schedulers.DPMSolverMultistepScheduler",
    "diffusers.DPMSolverMultistepScheduler": "mindone.diffusers.schedulers.DPMSolverMultistepScheduler",
}

diffusers_pipeline_map = {
    "diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion.StableDiffusionPipeline": "mindone.diffusers.pipelines.StableDiffusionPipeline",
    "diffusers.StableDiffusionPipeline": "mindone.diffusers.pipelines.StableDiffusionPipeline",
    "diffusers.pipelines.stable_diffusion_xl.StableDiffusionXLPipeline": "mindone.diffusers.pipelines.StableDiffusionXLPipeline",
    "diffusers.StableDiffusionXLPipeline": "mindone.diffusers.pipelines.StableDiffusionXLPipeline",
}

diffusers_encoder_map = {
    "diffusers.models.transformers.transformer_2d.Transformer2DModel": "mindone.diffusers.models.transformers.Transformer2DModel",
    "diffusers.Transformer2DModel": "mindone.diffusers.models.transformers.Transformer2DModel",
}

t2m_map = {
    "torch.Tensor": "mindspore.Tensor",
    "torch.tensor": "mindspore.Tensor",
    "torch.ByteTensor": "mindspore.Tensor",
    "torch.IntTensor": "mindspore.Tensor",
    "torch.FloatTensor": "mindspore.Tensor",
    "torch.LongTensor": "mindspore.Tensor",
    "torch.BoolTensor": "mindspore.Tensor",
    "torch.float": "mindspore.float32",
    "torch.double": "mindspore.float64",
    "torch.float32": "mindspore.float32",
    "torch.float64": "mindspore.float64",
    "torch.float16": "mindspore.float16",
    "torch.bfloat16": "mindspore.bfloat16",
    "torch.int8": "mindspore.int8",
    "torch.uint8": "mindspore.uint8",
    "torch.int16": "mindspore.int16",
    "torch.int": "mindspore.int32",
    "torch.int32": "mindspore.int32",
    "torch.int64": "mindspore.int64",
    "torch.long": "mindspore.int64",
    "torch.bool": "mindspore.bool_",
    "torch.dtype": "mindspore.Type",
    "torch.Generator": "mindspore.Generator",
    "torch.complex64": "mindspore.complex64",
    "torch.no_grad": "mindspore._no_grad",
    "torch.version": "mindspore.version",
    "torch.vmap": "mindspore.vmap",
    "torch.nn.Parameter": "mindspore.Parameter",
    "torch.from_numpy": "mindspore.Tensor.from_numpy",
}


class TorchToMindsporeCST(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider, ParentNodeProvider)

    def __init__(self, filename):
        self.unmapped: Set[str] = set()
        self.need_mint_import = False
        self.filename = filename
        self.need_ms_import = False
        self.need_ops_import = False
        self.unmapped_details: Set[Tuple[str, int, str]] = set()
        self.has_map_details: Set[Tuple[str, int, str]] = set()
        self.import_as_other = dict()
        self.from_import_as_other = dict()
        self.need_use_peft_backend_false = False

    def leave_Module(self, original_node, updated_node):
        # Insert necessary imports at the beginning
        insert_lines = []
        if self.need_ms_import:
            insert_lines.append(
                cst.SimpleStatementLine(
                    [
                        cst.Import(
                            names=[
                                cst.ImportAlias(
                                    name=cst.Name("mindspore"),
                                    asname=cst.AsName(name=cst.Name("ms")),
                                )
                            ]
                        )
                    ]
                )
            )
        if self.need_ops_import:
            insert_lines.append(
                cst.SimpleStatementLine(
                    [
                        cst.ImportFrom(
                            module=cst.Name("mindspore"),
                            names=[cst.ImportAlias(name=cst.Name("ops"))],
                        )
                    ]
                )
            )
        if self.need_mint_import:
            insert_lines.append(
                cst.SimpleStatementLine(
                    [
                        cst.ImportFrom(
                            module=cst.Name("mindspore"),
                            names=[
                                cst.ImportAlias(name=cst.Name("mint")),
                                cst.ImportAlias(name=cst.Name("nn")),
                            ],
                        )
                    ]
                )
            )

        # Find the end of the import block to insert USE_PEFT_BACKEND
        # This needs to be after all imports, with a blank line separator
        if self.need_use_peft_backend_false:
            new_body = list(insert_lines) + list(updated_node.body)
            # Find the index after the last import statement
            import_block_end = len(insert_lines)  # Start after inserted imports
            for i, stmt in enumerate(updated_node.body):
                if isinstance(
                    stmt,
                    (cst.Import, cst.ImportFrom, cst.SimpleStatementLine),
                ):
                    import_block_end = len(insert_lines) + i + 1
                elif isinstance(stmt, cst.EmptyLine):
                    # Continue through empty lines at the beginning
                    continue
                else:
                    # Stop at first non-import, non-empty line
                    break

            # Insert USE_PEFT_BACKEND = False after import block
            # Add blank line before the assignment
            peft_statement = cst.SimpleStatementLine(
                [
                    cst.Assign(
                        targets=[cst.AssignTarget(target=cst.Name("USE_PEFT_BACKEND"))],
                        value=cst.Name("False"),
                    )
                ]
            )
            new_body.insert(import_block_end, cst.EmptyLine(indent=""))
            new_body.insert(import_block_end + 1, peft_statement)
            return updated_node.with_changes(body=new_body)

        if insert_lines:
            return updated_node.with_changes(body=insert_lines + list(updated_node.body))
        return updated_node

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        if original_node.name.value == "forward":
            return updated_node.with_changes(name=cst.Name("construct"))
        return updated_node

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.BaseStatement:
        # If the left and right sides of the assignment are identical, e.g., tensor = tensor
        if (
            isinstance(updated_node.value, cst.Name)
            and isinstance(updated_node.targets[0].target, cst.Name)
            and updated_node.value.value == updated_node.targets[0].target.value
        ):
            return cst.RemoveFromParent()
        return updated_node

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.BaseExpression:
        parent = self.get_metadata(cst.metadata.ParentNodeProvider, original_node, default=None)

        # 1. If Attribute is ImportAlias.name (full attribute chain in an import ... statement)
        if isinstance(parent, cst.ImportAlias):
            # Only process if the name of this ImportAlias is the current node
            if parent.name is original_node:
                # _get_fullname returns the full chain, e.g., torch.utils.checkpoint

                full = self._get_fullname(updated_node)
                # print(parent.asname)
                if parent.asname is not None:
                    alias_name = parent.asname.name.value  # Get the name after as, e.g., "nn"
                    self.import_as_other[alias_name] = full
                mapped = self._map_fullname(full, original_node)
                if mapped:
                    return self._str_to_attr(mapped)
                return updated_node
            else:
                # This means it's an intermediate node (like torch or utils), skip processing and return updated_node
                return updated_node

        # 2. If Attribute is an attribute in ImportFrom.module (from ... import ...)
        if isinstance(parent, cst.ImportFrom):
            # This part is handled by leave_ImportFrom, so we skip it here
            return updated_node

        full = self._get_fullname(updated_node)
        mapped = self._map_fullname(full, original_node)
        if mapped:
            return self._str_to_attr(mapped)
        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        # Handle torch.is_grad_enabled() - remove entirely (return True)
        if m.matches(updated_node.func, m.Attribute(attr=m.Name("is_grad_enabled"))):
            # Match any value that is a Name (e.g., torch, ms, mindspore)
            value = updated_node.func.value
            if m.matches(value, m.Name()):
                # Replace with True
                return cst.Name("True")

        if m.matches(updated_node.func, m.Attribute(attr=m.Name("new_tensor"))):
            if isinstance(updated_node.func, cst.Attribute) and isinstance(updated_node.func.value, cst.Name):
                tensor_name = updated_node.func.value.value
                new_func = cst.Attribute(value=cst.Name("mindspore"), attr=cst.Name("tensor"))
                dtype_arg = cst.Arg(
                    keyword=cst.Name("dtype"),
                    value=cst.Attribute(value=cst.Name(tensor_name), attr=cst.Name("dtype")),
                )
                # print(updated_node.args, dtype_arg)
                return cst.Call(func=new_func, args=updated_node.args + (dtype_arg,))

        if m.matches(updated_node.func, m.Attribute(attr=m.Name("size"))):
            target = updated_node.func.value
            if not updated_node.args:
                return cst.Attribute(value=target, attr=cst.Name("shape"))
            if len(updated_node.args) == 1:
                return cst.Subscript(
                    value=cst.Attribute(value=target, attr=cst.Name("shape")),
                    slice=[cst.SubscriptElement(slice=updated_node.args[0].value)],
                )
        # Handle super().forward() -> super().construct()
        if m.matches(updated_node.func, m.Attribute(attr=m.Name("forward"))):
            if m.matches(updated_node.func.value, m.Call(func=m.Name("super"))):
                return updated_node.with_changes(func=cst.Attribute(value=updated_node.func.value, attr=cst.Name("construct")))

        delete_args = False
        new_args = []
        for arg in updated_node.args:
            if not (arg.keyword and arg.keyword.value == "device") and not m.matches(arg.value, m.Attribute(attr=m.Name("device"))):
                new_args.append(arg)
            else:
                delete_args = True
        if not new_args and delete_args:
            if isinstance(updated_node.func, cst.Attribute):
                return updated_node.func.value
        return updated_node.with_changes(args=new_args)
        # return updated_node

    def leave_Import(self, original_node: cst.Import, updated_node: cst.Import) -> cst.BaseStatement:
        new_aliases: list[cst.ImportAlias] = []
        for alias in updated_node.names:
            full_name = self._get_fullname(alias.name)
            if full_name == "torch":  # import torch -> import mindspore
                self.need_ms_import = True
                new_aliases.append(
                    cst.ImportAlias(
                        name=cst.Name("mindspore"),
                        # asname=cst.AsName(name=cst.Name("ms"))
                    )
                )
            elif full_name.startswith("torch.nn"):
                # import torch.nn as nn -> import mindspore.mint.nn as nn
                # import torch.nn -> import mindspore.mint.nn
                self.need_mint_import = True
                new_name = full_name.replace("torch.nn", "mindspore.mint.nn", 1)
                new_aliases.append(cst.ImportAlias(name=self._str_to_attr(new_name), asname=alias.asname))
            else:
                new_aliases.append(alias)

        if not new_aliases:
            return cst.RemoveFromParent()
        return updated_node.with_changes(names=new_aliases)

    def get_importfrom_asname(self, original_node: cst.ImportFrom):
        # Get the import source (e.g., torch.nn)
        base_module = self._get_fullname(original_node.module)

        for alias in original_node.names:
            if isinstance(alias, cst.ImportAlias):
                # Get the imported name (e.g., functional)
                imported_name = alias.name.value if isinstance(alias.name, cst.Name) else self._get_fullname(alias.name)
                full_name = f"{base_module}.{imported_name}"
                if full_name.startswith("torch.") and alias.asname:
                    asname = alias.asname.name.value
                    skip = False
                    for v in self.from_import_as_other.values():
                        if full_name.startswith(v) and len(full_name) < len(v):
                            skip = True
                            break
                        if v.startswith(full_name) and len(v) > len(full_name):
                            # Remove old short prefixes
                            keys_to_remove = [k for k, val in self.from_import_as_other.items() if val == v]
                            for k in keys_to_remove:
                                del self.from_import_as_other[k]
                elif full_name.startswith("torch.") and not alias.asname:
                    asname = full_name.split(".")[-1]
                    self.from_import_as_other[asname] = full_name

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.BaseStatement:
        if updated_node.module is None:
            return updated_node

        # Detect utils imports by checking module attribute directly
        # Handles both absolute (diffusers.utils) and relative ...utils imports
        is_utils_import = False
        if updated_node.module:
            if isinstance(updated_node.module, cst.Attribute):
                # Check if the last attr name is "utils"
                if isinstance(updated_node.module.attr, cst.Name):
                    is_utils_import = updated_node.module.attr.value == "utils"
            elif isinstance(updated_node.module, cst.Name):
                # Relative import: from ...utils import
                is_utils_import = updated_node.module.value == "utils"

        if is_utils_import:
            # Remove USE_PEFT_BACKEND, replace_example_docstring, is_torch_xla_available from import
            names_to_remove = {"USE_PEFT_BACKEND", "replace_example_docstring", "is_torch_xla_available"}
            
            new_names = [
                name for name in updated_node.names 
                if not (
                    isinstance(name, cst.ImportAlias) and 
                    isinstance(name.name, cst.Name) and 
                    name.name.value in names_to_remove
                )
            ]
            
            if not new_names:
                return cst.RemoveFromParent()
            
            return updated_node.with_changes(names=new_names)

        # Get the module string for further processing
        module_str = self._get_fullname(updated_node.module)

        # Handle utils.torch_utils -> utils.mindspore_utils transformation
        if ".torch_utils" in module_str:
            # Replace torch_utils with mindspore_utils
            new_module_str = module_str.replace(".torch_utils", ".mindspore_utils", 1)
            new_module_expr = self._str_to_attr(new_module_str)
            self.get_importfrom_asname(original_node)
            return updated_node.with_changes(module=new_module_expr)

        # Handle torch imports
        if not module_str.startswith("torch"):
            return updated_node
        if module_str.startswith("torch.nn"):
            # from torch.nn import xx -> from mindspore.mint.nn import xx
            new_module_str = module_str.replace("torch.nn", "mindspore.mint.nn", 1)
            self.need_mint_import = True
        elif module_str.startswith("torch"):
            # from torch import xx -> from mindspore import xx
            new_module_str = module_str.replace("torch", "mindspore", 1)

        new_module_expr = self._str_to_attr(new_module_str)
        self.get_importfrom_asname(original_node)
        return updated_node.with_changes(module=new_module_expr)

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.CSTNode:
        # Handle self.maybe_free_model_hooks
        for expr in updated_node.body:
            if m.matches(
                expr,
                m.Expr(value=m.Call(func=m.Attribute(value=m.Name("self"), attr=m.Name("maybe_free_model_hooks")))),
            ):
                return cst.RemoveFromParent()

        return updated_node

    def _map_fullname(self, name: str, node):
        pos = self.get_metadata(PositionProvider, node)
        if name.split(".")[0] in self.import_as_other:
            name = self.import_as_other[name.split(".")[0]] + "." + ".".join(name.split(".")[1:])
        if name.split(".")[0] in self.from_import_as_other:  # e.g. from torch.nn.functional import softmax as soft -> soft()
            name = self.from_import_as_other[name.split(".")[0]] + "." + ".".join(name.split(".")[1:])
        if name in mint_nn_map:
            self.need_mint_import = True
            self.has_map_details.add((self.filename, pos.start.line, name))
            return mint_nn_map[name]
        elif "torch." + name in mint_nn_map:
            self.need_mint_import = True
            self.has_map_details.add((self.filename, pos.start.line, name))
            return mint_nn_map["torch." + name]
        elif name in mint_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            self.need_mint_import = True
            return mint_map[name]
        elif name in t2m_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            self.need_ms_import = True
            return t2m_map[name]
        elif name in ops_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            self.need_ops_import = True
            return ops_map[name]
        elif name in diffusers_qwen_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_qwen_map[name]
        elif name in diffusers_qwen_scheduler_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_qwen_scheduler_map[name]
        elif name in diffusers_qwen_model_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_qwen_model_map[name]
        elif name in diffusers_qwen_loader_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_qwen_loader_map[name]
        elif name in diffusers_utility_map:
            mapped = diffusers_utility_map[name]
            if mapped is None:
                return None  # Skip - mark as handled
            self.has_map_details.add((self.filename, pos.start.line, name))
            return mapped
        elif name in diffusers_transformers_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_transformers_map[name]
        elif name in diffusers_unet_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_unet_map[name]
        elif name in diffusers_vae_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_vae_map[name]
        elif name in diffusers_scheduler_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_scheduler_map[name]
        elif name in diffusers_pipeline_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_pipeline_map[name]
        elif name in diffusers_encoder_map:
            self.has_map_details.add((self.filename, pos.start.line, name))
            return diffusers_encoder_map[name]
        elif name.startswith("torch.") and node:
            self.unmapped_details.add((self.filename, pos.start.line, name))
        elif name.startswith("diffusers.") and node:
            self.unmapped_details.add((self.filename, pos.start.line, name))
        return None

    def _dedup_unmapped_details(self):
        new_details = set()
        temp = {}
        for item in self.unmapped_details:
            if item is None or len(item) != 3:
                continue
            filename, lineno, name = item
            if lineno is None:
                continue
            key = (filename, lineno)
            # Same line, skip if already replaced
            if any(filename == f and lineno == l for f, l, _ in self.has_map_details):
                continue
            # For torch.nn and torch.nn.functional, remove torch.nn
            if key not in temp:
                temp[key] = name
            else:
                if len(name) > len(temp[key]):
                    temp[key] = name

        for (filename, lineno), name in temp.items():
            # If there are multiple replacements of the same operator in the file, skip to avoid log explosion
            if any(filename == f and name == n for f, _, n in new_details):
                continue
            if any(name in full for _, full in self.import_as_other.items()):
                continue
            if any(name in full for _, full in self.from_import_as_other.items()):
                continue
            new_details.add((filename, lineno, name))
        self.unmapped_details = new_details

    def _get_fullname(self, node: cst.CSTNode) -> str:
        """Recursively parse a chain of Attribute/Name nodes, avoiding reliance on the .code attribute."""
        if isinstance(node, cst.Name):
            return node.value
        if isinstance(node, cst.Attribute):
            left = self._get_fullname(node.value)
            right = self._get_fullname(node.attr)
            return f"{left}.{right}" if left else right
        return ""

    def _str_to_attr(self, dotted: str) -> cst.BaseExpression:
        parts = dotted.split(".")
        expr: cst.BaseExpression = cst.Name(parts[0])
        for part in parts[1:]:
            expr = cst.Attribute(value=expr, attr=cst.Name(part))
        return expr

def post_process_code(code: str) -> str:
    """
    Apply string replacements to the converted code.
    """
    # Handle XLA import removal
    lines = code.split("\n")
    new_lines = []
    in_xla_block = False

    for line in lines:
        if "if is_torch_xla_available():" in line:
            in_xla_block = True
            continue
        elif in_xla_block:
            if line and not line.startswith(("    ", "\t")):
                in_xla_block = False
            continue
        if "is_torch_xla_available" in line and "import" in line:
            continue
        new_lines.append(line)

    code = "\n".join(new_lines)
    code = code.replace("XLA_AVAILABLE = False\n", "")
    code = re.sub(
        r'(\s*)if XLA_AVAILABLE:\s*\n\s*\1\s*xm\.mark_step\(\)',
        r'\1',
        code,
        flags=re.MULTILINE
    )

    # Remove duplicate mindspore import lines
    lines = code.split("\n")
    seen_import = False
    new_lines = []
    for line in lines:
        if line.strip() == "import mindspore" or line.strip() == "import mindspore as ms":
            if not seen_import:
                new_lines.append("import mindspore as ms")
                seen_import = True
        else:
            new_lines.append(line)
    code = "\n".join(new_lines)

    # mindspore. -> ms.
    code = code.replace("mindspore.", "ms.")

    # ms.mint -> mint
    code = code.replace("ms.mint.", "mint.")

    if "from mindspore import mint" not in code and "mint." in code:
        if "import mindspore as ms" in code:
            code = code.replace(
                "import mindspore as ms",
                "import mindspore as ms\nfrom mindspore import mint",
                1,
            )
        else:
            code = "from mindspore import mint\n" + code

    if "import mindspore as ms" not in code and "ms." in code:
        code = "import mindspore as ms\n" + code

    # Example docstring conversion: torch -> mindspore/mindone
    # Must be done before mindspore. -> ms. replacement
    code = code.replace("torch.bfloat16", "ms.bfloat16")
    code = code.replace(">>> import torch\n", ">>> import mindspore as ms\n")
    code = code.replace(">>> from diffusers", ">>> from mindone.diffusers")
    code = code.replace("torch_dtype=", "mindspore_dtype=")
    code = code.replace('.to("cuda")', "")

    # Clean up orphaned device = self._execution_device (handles inline assignments)
    code = re.sub(r'self\.__?execution_device\s*:\s*str\s*=\s*"cuda"', "", code)

    # Remove device-related usage
    # .to(device) and .to("cuda") / .to("cpu") calls
    code = re.sub(r".to\(device\)", "", code)
    code = re.sub(r'.to\(["\']cpu["\']\)', "", code)
    code = re.sub(r'.to\(["\']cuda["\']\)', "", code)
    code = re.sub(r".cuda\(\)", "", code)
    code = re.sub(r".cpu\(\)", "", code)

    # torch.cuda.* calls
    code = re.sub(r"torch\.cuda\.is_available\(\)", "True", code)

    # .to(device) with device on new line
    code = re.sub(r"\.to\(\s*\n\s*device\s*\n\s*\)", "", code)

    # device parameter annotations and default values
    code = re.sub(
        r"device\s*:\s*Optional\[Union\[str,\s*torch\.device\]\]\s*=\s*None(?:,\s*)?",
        "",
        code,
    )
    code = re.sub(r"device\s*:\s*Optional\[torch\.device\]\s*=\s*None(?:,\s*)?,", "", code)
    code = re.sub(
        r",\s*device\s*:\s*Optional\[Union\[str,\s*torch\.device\]\]\s*=\s*None",
        "",
        code,
    )
    code = re.sub(r",\s*device\s*:\s*Optional\[torch\.device\]\s*=\s*None", "", code)

    # device assignment patterns
    code = re.sub(r"\s*device\s*=\s*device\s+or\s+self\._execution_device", "", code)
    code = re.sub(r"\s*device\s*=\s*self\._execution_device", "", code)
    code = re.sub(r"device\s*=\s*device\s*\|\|\s*self\.\w+\._execution_device", "", code)
    code = re.sub(r"device\s*=\s*self\.\w+\._execution_device", "", code)

    # device parameter default values (additional patterns)
    code = re.sub(r",\s*device\s*=\s*None", "", code)
    code = re.sub(r",\s*device", "", code)
    code = re.sub(r',\s*device(?=\s*,|\s*\))', "", code)

    # torch.device() calls and assignments
    lines = code.split("\n")
    new_lines = []
    for line in lines:
        # Skip lines like "device = torch.device("cuda")"
        if re.match(r"^\s*device\s*=\s*torch\.device\(", line):
            continue
        # Skip lines like "device = "cuda""
        if re.match(r'^\s*device\s*=\s*["\']cuda["\']', line):
            continue
        # Skip lines like "device = "cpu""
        if re.match(r'^\s*device\s*=\s*["\']cpu["\']', line):
            continue
        new_lines.append(line)
    code = "\n".join(new_lines)

    # .images[0] -> [0][0] for mindone
    code = code.replace(".images[0]", "[0][0]")

    # Remove @replace_example_docstring decorators (simple string match)
    # Pattern: @replace_example_docstring(...) followed by optional blank lines
    lines = code.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if line contains @replace_example_docstring
        if re.match(r"^\s*@replace_example_docstring\(", line):
            # Skip this decorator line
            i += 1
            # Skip any following blank/empty lines
            while i < len(lines) and lines[i].strip() == "":
                i += 1
        else:
            new_lines.append(line)
            i += 1
    code = "\n".join(new_lines)

    # fix import commas
    lines = code.split('\n')
    fixed_lines = []
    in_multiline_import = False  # 标记是否在多行import括号内

    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # 检测多行import开始
        if stripped.startswith('from ') and '(' in stripped and not in_multiline_import:
            in_multiline_import = True
            fixed_lines.append(line)
            continue
        
        # 如果在多行import内
        if in_multiline_import:
            # 检查是否是结束括号
            if ')' in stripped:
                in_multiline_import = False
                # 检查最后一行是否有逗号
                if stripped.endswith(','):
                    fixed_lines.append(line.rstrip().rstrip(','))
                else:
                    fixed_lines.append(line)
            else:
                # 在多行import中间，不处理逗号（保持原样）
                fixed_lines.append(line)
            continue
        
        # 普通单行import处理
        if ('import' in line or 'from' in line) and line.strip().endswith(','):
            fixed_lines.append(line.rstrip().rstrip(','))
        else:
            fixed_lines.append(line)

    code = '\n'.join(fixed_lines)

    return code


def convert_file(path: str, transformer_class):
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"[ERROR] Failed to process {path}: {e}")

    try:
        all_unmapped: Set[Tuple[str, int, str]] = set()
        tree = cst.parse_module(source)
        wrapper = MetadataWrapper(tree)
        transformer = transformer_class(filename=path)
        modified_tree = wrapper.visit(transformer)
        transformer._dedup_unmapped_details()

        modified_code = modified_tree.code
        modified_code = post_process_code(modified_code)
        with open(path, "w", encoding="utf-8") as f:
            f.write(modified_code)
        unmapped = transformer.unmapped_details
        all_unmapped.update(unmapped)
        if all_unmapped:
            for file, line, name in sorted(all_unmapped):
                print(f"- {name} ({file}:{line})")
    except Exception as e:
        print(f"[ERROR] Failed to process {path}: {e}")


def convert_specific_files(src_root: str, dst_root: str, file_patterns: list[str] = None):
    """
    Convert only specific Python files from source to destination.

    Args:
        src_root: Source directory root
        dst_root: Destination directory root
        file_patterns: List of file patterns relative to src_root (e.g., ["models/controlnet.py", "pipelines/stable_diffusion/*.py"])

    For file_patterns:
        - If ends with .py: converts that specific file
        - Uses glob patterns (e.g., "pipelines/flux/*.py" matches all python files in flux directory)
    """
    if not file_patterns:
        # If no patterns specified, fall back to original behavior (convert all)
        print("[WARNING] No file patterns specified. Converting ALL Python files in the source directory.")
        copy_and_convert_all(src_root, dst_root)
        return

    print("The following interfaces have not been replaced yet. Please modify the corresponding code based on the location indicated in the logs.")

    # Process each pattern
    for pattern in file_patterns:
        # Normalize path separator
        pattern = pattern.replace("/", os.sep).replace("\\", os.sep)
        src_pattern = os.path.join(src_root, pattern)

        # Use glob to find matching files
        import glob as glob_module

        matched_files = glob_module.glob(src_pattern, recursive=True)

        if not matched_files:
            print(f"[WARNING] No files found matching pattern: {pattern}")
            continue

        for src_file in matched_files:
            # Get relative path from src_root
            rel_path = os.path.relpath(src_file, src_root)
            dst_file = os.path.join(dst_root, rel_path)

            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)

            # Copy source file to destination
            shutil.copy2(src_file, dst_file)

            # Convert the file
            convert_file(dst_file, TorchToMindsporeCST)
            print(f"[+] Converted: {rel_path}")


def copy_and_convert_all(src_root: str, dst_root: str):
    """
    Convert ALL Python files from source to destination (original behavior).
    """
    shutil.copytree(src_root, dst_root, dirs_exist_ok=True)
    print("The following interfaces have not been replaced yet. Please modify the corresponding code based on the location indicated in the logs.")
    for dirpath, _, filenames in os.walk(dst_root):
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                convert_file(filepath, TorchToMindsporeCST)


def main():
    parser = argparse.ArgumentParser(description=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--src_root", type=str, help="Source directory to convert.")
    group.add_argument("--src_file", type=str, help="Single Python file to convert.")
    parser.add_argument("--dst_root", type=str, help="Destination directory for folder conversion.")
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Convert the --src_file in place.",
    )
    parser.add_argument(
        "--files",
        type=str,
        nargs="*",
        help=(
            "Specific file patterns to convert (relative to src_root). "
            "If not specified, ALL Python files will be converted. "
            'Example: --files "models/controlnet.py" "pipelines/flux/*.py"'
        ),
    )
    args = parser.parse_args()

    if args.src_file:
        if not args.inplace:
            raise SystemExit("Use --inplace when converting a single file with --src_file.")
        convert_file(args.src_file, TorchToMindsporeCST)
        print(f"[+] Converted file in place {args.src_file}")
        return

    if not args.dst_root:
        raise SystemExit("Use --dst_root when converting a folder with --src_root.")

    # Use selective file conversion if --files is specified
    if args.files:
        convert_specific_files(args.src_root, args.dst_root, args.files)
    else:
        # Convert all files (original behavior)
        print("[WARNING] No --files specified. Converting ALL Python files.")
        copy_and_convert_all(args.src_root, args.dst_root)
    print(f"[+] Converted folder {args.src_root} to {args.dst_root}")


if __name__ == "__main__":
    main()
