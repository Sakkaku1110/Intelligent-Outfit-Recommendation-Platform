import torch

from outfit_recommender.model import OutfitCompatibilityModel


def test_model_handles_variable_length_outfits() -> None:
    model = OutfitCompatibilityModel(
        embedding_dim=32,
        category_dim=8,
        transformer_layers=1,
        attention_heads=4,
        pretrained_backbone=False,
    )
    images = torch.randn(2, 4, 3, 64, 64)
    categories = torch.tensor([[1, 2, 5, 0], [3, 5, 4, 8]])
    mask = torch.tensor(
        [[True, True, True, False], [True, True, True, True]]
    )

    logits = model(images, categories, mask)
    loss = torch.nn.functional.binary_cross_entropy_with_logits(
        logits, torch.tensor([1.0, 0.0])
    )
    loss.backward()

    assert logits.shape == (2,)
    assert torch.isfinite(loss)
