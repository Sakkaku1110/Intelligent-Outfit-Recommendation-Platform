import torch
from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from .constants import SEMANTIC_CATEGORIES


class OutfitCompatibilityModel(nn.Module):
    def __init__(
        self,
        embedding_dim: int = 256,
        category_dim: int = 32,
        transformer_layers: int = 2,
        attention_heads: int = 4,
        dropout: float = 0.2,
        pretrained_backbone: bool = True,
        freeze_backbone: bool = False,
    ) -> None:
        super().__init__()
        weights = (
            MobileNet_V3_Small_Weights.DEFAULT if pretrained_backbone else None
        )
        backbone = mobilenet_v3_small(weights=weights)
        self.image_backbone = backbone.features
        self.image_pool = nn.AdaptiveAvgPool2d(1)
        backbone_dim = 576

        self.image_projection = nn.Sequential(
            nn.Linear(backbone_dim, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.GELU(),
        )
        self.category_embedding = nn.Embedding(
            len(SEMANTIC_CATEGORIES), category_dim, padding_idx=0
        )
        token_dim = embedding_dim + category_dim
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=token_dim,
            nhead=attention_heads,
            dim_feedforward=token_dim * 2,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=False,
        )
        self.outfit_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=transformer_layers,
            enable_nested_tensor=False,
        )
        self.classifier = nn.Sequential(
            nn.LayerNorm(token_dim),
            nn.Linear(token_dim, embedding_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embedding_dim, 1),
        )

        self.backbone_frozen = freeze_backbone
        if self.backbone_frozen:
            for parameter in self.image_backbone.parameters():
                parameter.requires_grad = False

    def train(self, mode: bool = True):
        super().train(mode)
        if self.backbone_frozen:
            self.image_backbone.eval()
        return self

    def forward(
        self,
        images: torch.Tensor,
        categories: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        batch_size, item_count = images.shape[:2]
        flat_images = images.reshape(batch_size * item_count, *images.shape[2:])
        image_features = self.image_backbone(flat_images)
        image_features = self.image_pool(image_features).flatten(1)
        image_features = self.image_projection(image_features)
        image_features = image_features.reshape(batch_size, item_count, -1)

        category_features = self.category_embedding(categories)
        tokens = torch.cat((image_features, category_features), dim=-1)
        tokens = self.outfit_encoder(tokens, src_key_padding_mask=~mask)
        pooled = (tokens * mask.unsqueeze(-1)).sum(dim=1)
        pooled = pooled / mask.sum(dim=1, keepdim=True).clamp_min(1)
        return self.classifier(pooled).squeeze(-1)

    def config(self) -> dict:
        first_projection = self.image_projection[0]
        category_dim = self.category_embedding.embedding_dim
        encoder_layer = self.outfit_encoder.layers[0]
        return {
            "embedding_dim": first_projection.out_features,
            "category_dim": category_dim,
            "transformer_layers": len(self.outfit_encoder.layers),
            "attention_heads": encoder_layer.self_attn.num_heads,
            "dropout": encoder_layer.dropout.p,
            "pretrained_backbone": False,
            "freeze_backbone": self.backbone_frozen,
        }
