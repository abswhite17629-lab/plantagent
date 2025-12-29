import torch
import torch.nn as nn
from .attention import Attention

class Block(nn.Module):
    def __init__(self, c1, c2, k=3, s=1, d=1, g=1):
        super().__init__()
        self.conv = nn.Conv2d(c1, c2, k, s, d, groups=g, bias=False)
        self.bn = nn.BatchNorm2d(c2)
        self.act = nn.SiLU()
        self.attn = Attention(c2) if c2 > 128 else nn.Identity()

    def forward(self, x):
        return self.attn(self.act(self.bn(self.conv(x))))
