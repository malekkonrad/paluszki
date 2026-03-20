from src.models.cnn_transformer.pipeline import CNNTransformerPipeline


PIPELINE_REGISTRY = {
    "cnn_transformer": CNNTransformerPipeline,
}