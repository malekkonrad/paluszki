from src.models.cnn_transformer.pipeline import CNNTransformerPipeline
from src.models.keypoint_transformer.pipeline import KeypointTransformerPipeline


PIPELINE_REGISTRY = {
    "cnn_transformer": CNNTransformerPipeline,
    "keypoint_transformer": KeypointTransformerPipeline,
}