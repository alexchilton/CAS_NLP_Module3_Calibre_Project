# genre_classifier.py

import os
from typing import List, Tuple, Optional

import joblib
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


class GenreClassifier:
    def __init__(self, model_dir: str = "genre_model", device: Optional[str] = None):
        self.model_dir = model_dir

        # Device
        if device is not None:
            self.device = torch.device(device)
        else:
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            elif torch.backends.mps.is_available():
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")


        # Load model + tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()

        # Load MultiLabelBinarizer
        lb_path = os.path.join(model_dir, "label_binarizer.pkl")
        self.mlb = joblib.load(lb_path)
        self.label_names = list(self.mlb.classes_)

    @torch.no_grad()
    def predict(
        self,
        title: Optional[str],
        description: Optional[str],
        threshold: float = 0.5,
        top_k: Optional[int] = None,
        max_length: int = 256,
    ) -> List[Tuple[str, float]]:
        """
        Return list of (genre, probability) sorted by probability desc.

        - threshold: probability cutoff for keeping a label
        - top_k: if set, keep at most top_k labels (after thresholding)
        """
        title = title or ""
        description = description or ""
        text = (title + " " + description).strip()

        if not text:
            return []

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        logits = self.model(**inputs).logits
        probs = torch.sigmoid(logits).cpu().numpy()[0]

        # indices above threshold
        idxs = np.where(probs >= threshold)[0].tolist()
        pairs = [(self.label_names[i], float(probs[i])) for i in idxs]

        # if nothing passes threshold, take the best one
        if not pairs:
            best = int(np.argmax(probs))
            pairs = [(self.label_names[best], float(probs[best]))]

        # sort & maybe truncate
        pairs.sort(key=lambda x: x[1], reverse=True)
        if top_k is not None:
            pairs = pairs[:top_k]

        return pairs

    @torch.no_grad()
    def predict_labels(
        self,
        title: Optional[str],
        description: Optional[str],
        threshold: float = 0.5,
        top_k: Optional[int] = None,
    ) -> List[str]:
        """Convenience: just the genre names."""
        pairs = self.predict(title, description, threshold, top_k)
        return [label for label, _ in pairs]
