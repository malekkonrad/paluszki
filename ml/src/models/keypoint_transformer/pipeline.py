import torch
import torch.nn as nn

from src.data.keypoint_extractor import KEYPOINT_DIM
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
        return x + self.pe[:, : x.size(1), :]


class KeypointTransformerPipeline(BasePipeline):
    """Sign-language translation pipeline using MediaPipe keypoints as input.

    Instead of raw pixels the model receives per-frame skeleton keypoints
    (pose + both hands, 225 floats per frame), which dramatically reduces the
    input dimensionality and gives the model a strong inductive bias towards
    the body parts that matter for sign language.

    Batch["frames"] shape expected: [B, T, KEYPOINT_DIM]  (KEYPOINT_DIM = 225)
    """

    def __init__(self, cfg, tokenizer):
        super().__init__()
        vocab_size = tokenizer.vocab_size()
        model_cfg = cfg["model"]

        d_model = model_cfg["d_model"]
        nhead = model_cfg["nhead"]
        num_layers = model_cfg["num_layers"]
        dropout = model_cfg["dropout"]
        kp_dim = model_cfg.get("keypoint_dim", KEYPOINT_DIM)

        # --- Keypoint encoder ---
        # Project raw keypoints → d_model with layer norm for stable training
        self.kp_proj = nn.Sequential(
            nn.Linear(kp_dim, d_model),
            nn.LayerNorm(d_model),
        )

        self.pos_enc_video = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=4 * d_model,
            dropout=dropout,
            batch_first=True,
        )
        self.temporal_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # --- Text decoder (identical to CNNTransformerPipeline) ---
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
        self.criterion = nn.CrossEntropyLoss(
            ignore_index=tokenizer.pad_id,
            label_smoothing=model_cfg.get("label_smoothing", 0.1),
        )
        self.tokenizer = tokenizer

    def encode_keypoints(self, keypoints):
        """Encode keypoint sequence to memory.

        Args:
            keypoints: [B, T, kp_dim]
        Returns:
            memory: [B, T, d_model]
        """
        x = self.kp_proj(keypoints)         # [B, T, d_model]
        x = self.pos_enc_video(x)
        memory = self.temporal_encoder(x)
        return memory

    def _forward_impl(self, keypoints, tgt_input_ids):
        memory = self.encode_keypoints(keypoints)

        tgt = self.token_embed(tgt_input_ids)
        tgt = self.pos_enc_text(tgt)

        seq_len = tgt.size(1)
        tgt_mask = nn.Transformer.generate_square_subsequent_mask(seq_len).to(tgt.device)

        decoded = self.text_decoder(
            tgt=tgt,
            memory=memory,
            tgt_mask=tgt_mask,
        )

        return self.output_head(decoded)

    def forward(self, batch):
        keypoints = batch["frames"]   # [B, T, kp_dim]
        tokens = batch["tokens"]

        tgt_inp = tokens[:, :-1]
        logits = self._forward_impl(keypoints, tgt_inp)

        return {"logits": logits}

    def compute_loss(self, batch, outputs):
        tokens = batch["tokens"]
        tgt_out = tokens[:, 1:]
        logits = outputs["logits"]

        loss = self.criterion(
            logits.reshape(-1, logits.size(-1)),
            tgt_out.reshape(-1),
        )

        return {"loss": loss}

    @torch.no_grad()
    def greedy_decode(self, keypoints, max_len=40):
        """Autoregressively decode keypoints to a token sequence.

        Args:
            keypoints: [T, kp_dim]  (single sample, no batch dim)
        Returns:
            list[int] — decoded token ids (including EOS if reached)
        """
        self.eval()
        keypoints = keypoints.unsqueeze(0)   # [1, T, kp_dim]
        generated = torch.tensor(
            [[self.tokenizer.bos_id]], dtype=torch.long, device=keypoints.device
        )

        for _ in range(max_len - 1):
            logits = self._forward_impl(keypoints, generated)
            next_token = logits[:, -1, :].argmax(dim=-1, keepdim=True)
            generated = torch.cat([generated, next_token], dim=1)

            if next_token.item() == self.tokenizer.eos_id:
                break

        return generated.squeeze(0).tolist()

    def decode_predictions(self, outputs):
        logits = outputs["logits"]
        pred_ids = logits.argmax(dim=-1)
        return [self.tokenizer.decode(row.tolist()) for row in pred_ids]
