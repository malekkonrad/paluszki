import torch


class SimpleTokenizer:
    def __init__(self, texts, min_freq=1):
        special_tokens = ["<pad>", "<bos>", "<eos>", "<unk>"]
        word_freq = {}

        for text in texts:
            for token in str(text).lower().strip().split():
                word_freq[token] = word_freq.get(token, 0) + 1

        vocab_words = [w for w, f in word_freq.items() if f >= min_freq]
        self.itos = special_tokens + sorted(vocab_words)
        self.stoi = {token: idx for idx, token in enumerate(self.itos)}

        self.pad_id = self.stoi["<pad>"]
        self.bos_id = self.stoi["<bos>"]
        self.eos_id = self.stoi["<eos>"]
        self.unk_id = self.stoi["<unk>"]

    def encode(self, text, max_len=40):
        tokens = str(text).lower().strip().split()
        ids = [self.bos_id]
        ids += [self.stoi.get(tok, self.unk_id) for tok in tokens]
        ids += [self.eos_id]
        ids = ids[:max_len]

        if len(ids) < max_len:
            ids += [self.pad_id] * (max_len - len(ids))

        return torch.tensor(ids, dtype=torch.long)

    def decode(self, ids):
        tokens = []
        for idx in ids:
            token = self.itos[idx]
            if token == "<eos>":
                break
            if token not in {"<pad>", "<bos>"}:
                tokens.append(token)
        return " ".join(tokens)

    def vocab_size(self):
        return len(self.itos)