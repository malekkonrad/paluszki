from src.models.cnn_transformer.pipeline import CNNTransformerPipeline
from src.models.keypoint_transformer.pipeline import KeypointTransformerPipeline
from src.models.keypoint_classifier.pipeline import KeypointClassifierPipeline


PIPELINE_REGISTRY = {
    "cnn_transformer": CNNTransformerPipeline,
    "keypoint_transformer": KeypointTransformerPipeline,
    "keypoint_classifier": KeypointClassifierPipeline,
}