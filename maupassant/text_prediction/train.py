import os
import json
import pickle
import shutil
import datetime

from comet_ml import Experiment
import tensorflow as tf

from maupassant.utils import timer
from maupassant.text_prediction.model import TensorflowModel
from maupassant.dataset.pandas import remove_rows_contains_null
from maupassant.text_prediction.dataset import DatasetGenerator
from maupassant.settings import API_KEY, PROJECT_NAME, WORKSPACE, MODEL_PATH

tf.compat.v1.disable_eager_execution()


class TrainerHelper(TensorflowModel):
    """Tool to train model."""

    def __init__(self, label_type, architecture, number_labels, vocab_size):
        self.model = tf.keras.Sequential()
        super().__init__(label_type, architecture, number_labels, vocab_size)

    @staticmethod
    def callback_func(checkpoint_path, tensorboard_dir=None):
        checkpoint = tf.keras.callbacks.ModelCheckpoint(filepath=checkpoint_path, verbose=1, period=5)
        if tensorboard_dir:
            tensorboard = tf.keras.callbacks.TensorBoard(log_dir=tensorboard_dir, histogram_freq=1)
            return [tensorboard, checkpoint]
        else:
            return [checkpoint]

    @timer
    def fit_model(self, train_dataset, val_dataset, epochs=30, callbacks=[]):
        return self.model.fit(train_dataset, epochs=epochs, validation_data=val_dataset, callbacks=callbacks)

    @staticmethod
    def define_paths(classifier, label):
        date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        name = f"{classifier}_{label}_{date}"
        base_dir = os.path.join(MODEL_PATH, name)

        return {
            "path": base_dir,
            "model_path": os.path.join(base_dir, 'model'),
            "model_plot":  os.path.join(base_dir, "model.jpg"),
            "model_info": os.path.join(base_dir, "model.json"),
            "metrics_path": os.path.join(base_dir, "metrics.json"),
            "tensorboard_path": os.path.join(base_dir, "tensorboard"),
            "checkpoint_path": os.path.join(base_dir, "checkpoint"),
        }

    @staticmethod
    def export_model_plot(path, model):
        tf.keras.utils.plot_model(model, to_file=path, show_shapes=True)

    @staticmethod
    def export_model(path, model):
        model.save(path)
        print(f"Model has been exported here => {path}")

    @staticmethod
    def export_encoder(directory, label_data):
        for k, v in label_data.items():
            path = os.path.join(directory, f"{v['id']}_{v['label_type']}_{k}_encoder.pkl")
            pickle.dump(v['encoder'], open(path, "wb"))
            print(f"{k} encoder has been exported here => {path}")

    @staticmethod
    def export_info(path, info):
        with open(path, 'w') as outfile:
            json.dump(info, outfile)
            print(f"Model information have been exported here => {path}")

    @staticmethod
    def export_metrics(path, metrics):
        with open(path, 'w') as outfile:
            json.dump(metrics, outfile)
            print(f"Model metrics have been exported here => {path}")


class Trainer(TrainerHelper):

    def __init__(
            self, dataset, architecture, feature, lang="english", words_predict=1, use_comet=True, epochs=10,
            batch_size=32, api_key=API_KEY, project_name=PROJECT_NAME, workspace=WORKSPACE):
        self.words_predict = words_predict
        self.lang = lang
        self.epochs = epochs
        self.label_type = "single-label"
        self.API_KEY = api_key
        self.PROJECT_NAME = project_name
        self.WORKSPACE = workspace
        self.use_comet = use_comet
        self.feature = feature
        dataset = remove_rows_contains_null(dataset, self.feature)
        self.__dataset__ = DatasetGenerator(batch_size=batch_size)
        self.train_dataset, self.test_dataset, self.val_dataset = self.__dataset__.generate(dataset[feature])
        self.label_encoder = {
            self.feature: {"encoder": self.__dataset__.le, "label_type": self.label_type, "id": self.words_predict}}
        super().__init__(self.label_type, architecture, self.__dataset__.max_labels, self.__dataset__.vocab_size)

    def main(self):
        self.set_model()
        self.compile_model()
        paths = self.define_paths(self.label_type, self.feature)
        os.mkdir(paths['path'])
        experiment = None

        if self.use_comet and self.API_KEY:
            experiment = Experiment(api_key=self.API_KEY, project_name=self.PROJECT_NAME, workspace=self.WORKSPACE)
            experiment.log_dataset_hash(self.train_dataset)
            experiment.add_tags(
                ['tensorflow', self.feature, self.architecture, self.embedding_type, self.lang, "words_prediction"])
            experiment.log_parameters(dict(enumerate(self.__dataset__.le.classes_)))
            with experiment.train():
                history = self.fit_model(self.train_dataset, self.val_dataset, epochs=self.epochs)
        elif self.use_comet:
            raise Exception("Please provide an api_key, project_name and workspace for comet_ml")
        else:
            callbacks = self.callback_func(
                tensorboard_dir=paths['tensorboard_path'], checkpoint_path=paths['checkpoint_path']
            )
            history = self.fit_model(self.train_dataset, self.val_dataset, epochs=self.epochs, callbacks=callbacks)
        loss = history.history["loss"]
        val_loss = history.history["val_loss"]
        macro_f1 = history.history["macro_f1"]
        val_macro_f1 = history.history["val_macro_f1"]
        metrics = {"loss": loss, "val_loss": val_loss, "macro_f1": macro_f1, "val_macro_f1": val_macro_f1}
        metrics = {metric: [round(float(value), 5) for value in values] for metric, values in metrics.items()}

        self.export_model(paths['model_path'], self.model)
        self.export_encoder(paths['path'], self.label_encoder)
        self.export_model_plot(paths['model_plot'], self.model)
        self.export_info(paths["model_info"], self.info)
        self.export_metrics(paths["metrics_path"], metrics)
        zip_model = shutil.make_archive(
            paths['path'], "zip", os.path.dirname(paths['path']), os.path.basename(paths['path'])
        )

        if self.use_comet:
            experiment.log_image(paths['model_plot'])
            experiment.log_asset(zip_model)
            experiment.end()

        return zip_model


if __name__ == '__main__':
    import pandas as pd
    from maupassant.settings import DATASET_PATH

    dataset_path = os.path.join(DATASET_PATH, "french_phrase.csv")
    dataset = pd.read_csv(dataset_path, nrows=50000)

    train = Trainer(dataset, "GRU", "agent_text", words_predict=1, epochs=3)
    model_path = train.main()
