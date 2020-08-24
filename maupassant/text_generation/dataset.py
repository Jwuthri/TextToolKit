import tqdm

import numpy as np
import tensorflow as tf

from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences

from maupassant.utils import timer
from maupassant.preprocessing.normalization import TextNormalization


class BuildDataset(object):

    def __init__(self, input_shape=64, max_labels=5000, batch_size=512, buffer_size=512, cleaning_func=None):
        self.normalizer = TextNormalization()
        self.input_shape = input_shape
        self.max_labels = max_labels
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.cleaning_func = cleaning_func
        self.tokenizer = Tokenizer(filters='', num_words=30000, oov_token='[UNK]')
        self.vocab_size = 0
        self.number_labels = 0

    def set_tokenizer(self, text):
        self.tokenizer.fit_on_texts([text])
        self.vocab_size = len(self.tokenizer.word_index) + 1

    def clean_dataset(self, data):
        pbar = tqdm.tqdm(total=len(data), desc="Cleaning the dataset")
        cleaned_texts = []
        for text in data.values:
            text = "[CLS]" + text
            text = self.normalizer.split_text_for_tokenizer(text)
            text = self.normalizer.replace_char_rep(text=text)
            text = self.normalizer.replace_words_rep(text=text)
            text = self.normalizer.text_demojis(text=text)
            text = self.normalizer.text_demoticons(text=text)
            if self.cleaning_func:
                text = self.cleaning_func(text)
            text = self.normalizer.remove_multiple_spaces(text=text)
            text = text.strip()
            text += "[END]"
            cleaned_texts.append(text)
            pbar.update(1)
        pbar.close()

        return cleaned_texts

    @staticmethod
    def concat_text(text):
        return " ".join(text)

    def predictable_words(self):
        value = min(self.tokenizer.num_words, self.max_labels)
        self.number_labels = value
        words = list(range(1, value))

        return words

    def texts_to_sequences(self, cleaned_data, labels, dataset_name):
        texts_to_sequences = list()
        pbar = tqdm.tqdm(total=len(cleaned_data), desc=f"Creating the dataset {dataset_name}")
        for text in cleaned_data:
            encoded_text = self.tokenizer.texts_to_sequences([text])[0]
            for idx in range(1, len(encoded_text) - 1):
                if encoded_text[idx:idx+1][0] in labels:
                    texts_to_sequences.append(encoded_text[:idx+1])
            pbar.update(1)
        pbar.close()

        return texts_to_sequences

    def create_dataset(self, data, labels, dataset_name):
        texts_to_sequences = self.texts_to_sequences(data, labels, dataset_name)
        padded_sequences = np.array(pad_sequences(texts_to_sequences, maxlen=self.input_shape + 1, padding='pre'))
        x, y = padded_sequences[:, :-1], padded_sequences[:, -1:]
        dataset = self.to_tensorflow_dataset(x, y)

        return dataset

    def to_tensorflow_dataset(self, x, y, is_training=True):
        dataset = tf.data.Dataset.from_tensor_slices((x, y))
        if is_training:
            dataset = dataset.cache()
            dataset = dataset.shuffle(buffer_size=self.buffer_size)

        dataset = dataset.batch(self.batch_size)
        dataset = dataset.prefetch(buffer_size=tf.data.experimental.AUTOTUNE)

        return dataset

    @timer
    def generate(self, data):
        cleaned_data = data[data.notnull()]
        cleaned_data = self.clean_dataset(cleaned_data)
        text = self.concat_text(cleaned_data)
        self.set_tokenizer(text)
        labels = self.predictable_words()
        _, test = train_test_split(cleaned_data, test_size=0.1, random_state=42)
        test, val = train_test_split(test, test_size=0.5, random_state=42)
        train_dataset = self.create_dataset(cleaned_data, labels, dataset_name='train')
        test_dataset = self.create_dataset(test, labels, dataset_name='test')
        val_dataset = self.create_dataset(val, labels, dataset_name='val')

        return train_dataset, test_dataset, val_dataset
