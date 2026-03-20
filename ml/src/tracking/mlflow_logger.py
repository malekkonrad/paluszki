import mlflow


class MLFlowLogger:
    def __init__(self, cfg):
        self.cfg = cfg
        self.enabled = cfg["mlflow"]["enabled"]

    def start_run(self):
        if not self.enabled:
            return
        mlflow.set_tracking_uri(self.cfg["mlflow"]["tracking_uri"])
        mlflow.set_experiment(self.cfg["mlflow"]["experiment_name"])
        mlflow.start_run(run_name=self.cfg["mlflow"]["run_name"])

    def log_params(self, params: dict):
        if not self.enabled:
            return
        flat = self._flatten_dict(params)
        for k, v in flat.items():
            mlflow.log_param(k, v)

    def log_metrics(self, metrics: dict, step: int):
        if not self.enabled:
            return
        for k, v in metrics.items():
            mlflow.log_metric(k, float(v), step=step)

    def set_tags(self, tags: dict):
        if not self.enabled:
            return
        mlflow.set_tags(tags)

    def log_artifact(self, path: str):
        if not self.enabled:
            return
        mlflow.log_artifact(path)

    def end_run(self):
        if not self.enabled:
            return
        mlflow.end_run()

    def _flatten_dict(self, d, parent_key="", sep="."):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)