import torch
import torch.nn as nn
import torchvision.models as models

from src.models.base import BasePipeline


class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=512):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32)
            * (-torch.log(torch.tensor(10000.0)) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class CNNTransformerPipeline(BasePipeline):
    def __init__(self, cfg, tokenizer):
        super().__init__()
        vocab_size = tokenizer.vocab_size()
        model_cfg = cfg["model"]

        d_model = model_cfg["d_model"]
        nhead = model_cfg["nhead"]
        num_layers = model_cfg["num_layers"]
        dropout = model_cfg["dropout"]
        pretrained_backbone = model_cfg.get("pretrained_backbone", True)

        backbone_weights = models.ResNet18_Weights.DEFAULT if pretrained_backbone else None
        backbone = models.resnet18(weights=backbone_weights)
        self.frame_encoder = nn.Sequential(*list(backbone.children())[:-1])
        self.visual_proj = nn.Linear(512, d_model)

        self.pos_enc_video = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=4 * d_model,
            dropout=dropout,
            batch_first=True,
        )
        self.temporal_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        self.token_embed = nn.Embedding(vocab_size, d_model)
        self.pos_enc_text = PositionalEncoding(d_model)

        decoder_layer = nn.TransformerDecoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=4 * d_model,
            dropout=dropout,
            batch_first=True,
        )
        self.text_decoder = nn.TransformerDecoder(decoder_layer, num_layers=num_layers)

        self.output_head = nn.Linear(d_model, vocab_size)
        self.criterion = nn.CrossEntropyLoss(ignore_index=tokenizer.pad_id)
        self.tokenizer = tokenizer

    def encode_video(self, frames):
        b, t, c, h, w = frames.shape
        x = frames.view(b * t, c, h, w)
        feats = self.frame_encoder(x).flatten(1)
        feats = self.visual_proj(feats)
        feats = feats.view(b, t, -1)
        feats = self.pos_enc_video(feats)
        memory = self.temporal_encoder(feats)
        return memory

    def _forward_impl(self, frames, tgt_input_ids):
        memory = self.encode_video(frames)

        tgt = self.token_embed(tgt_input_ids)
        tgt = self.pos_enc_text(tgt)

        seq_len = tgt.size(1)
        tgt_mask = nn.Transformer.generate_square_subsequent_mask(seq_len).to(tgt.device)

        decoded = self.text_decoder(
            tgt=tgt,
            memory=memory,
            tgt_mask=tgt_mask,
        )

        logits = self.output_head(decoded)
        return logits

    def forward(self, batch):
        frames = batch["frames"]
        tokens = batch["tokens"]

        tgt_inp = tokens[:, :-1]
        logits = self._forward_impl(frames, tgt_inp)

        return {
            "logits": logits,
        }

    def compute_loss(self, batch, outputs):
        tokens = batch["tokens"]
        tgt_out = tokens[:, 1:]
        logits = outputs["logits"]

        loss = self.criterion(
            logits.reshape(-1, logits.size(-1)),
            tgt_out.reshape(-1),
        )

        return {
            "loss": loss,
        }

    @torch.no_grad()
    def greedy_decode(self, frames, max_len=40):
        self.eval()
        frames = frames.unsqueeze(0)
        generated = torch.tensor([[self.tokenizer.bos_id]], dtype=torch.long, device=frames.device)

        for _ in range(max_len - 1):
            logits = self._forward_impl(frames, generated)
            next_token = logits[:, -1, :].argmax(dim=-1, keepdim=True)
            generated = torch.cat([generated, next_token], dim=1)

            if next_token.item() == self.tokenizer.eos_id:
                break

        return generated.squeeze(0).tolist()

    def decode_predictions(self, outputs):
        logits = outputs["logits"]
        pred_ids = logits.argmax(dim=-1)
        decoded = []

        for row in pred_ids:
            decoded.append(self.tokenizer.decode(row.tolist()))

        return decoded
