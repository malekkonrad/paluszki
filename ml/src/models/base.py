import torch.nn as nn

class BasePipeline(nn.Module):
    def forward(self, batch):
        raise NotImplementedError
    
    def compute_loss(self, batch, output):
        raise NotImplementedError
    
    def compute_predictions(self, batch, output):
        raise NotImplementedError