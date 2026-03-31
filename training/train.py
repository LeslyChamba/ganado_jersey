import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import MobileNetV2
from sklearn.model_selection import train_test_split
from PIL import Image
import os

IMG_SIZE = 224
DATA_PATH = "../dataset/images/"
LABELS_PATH = "../dataset/labels.csv"

# Cargar etiquetas
df = pd.read_csv(LABELS_PATH)

# Función para cargar imágenes
def load_image(path):
    img = Image.open(path).convert("RGB")
    img = img.resize((IMG_SIZE, IMG_SIZE))
    img = np.array(img) / 255.0
    return img

images = []
weights = []
bcs = []

for _, row in df.iterrows():
    img_path = os.path.join(DATA_PATH, row['imagen'])
    if os.path.exists(img_path):
        images.append(load_image(img_path))
        weights.append(row['peso'])
        bcs.append(row['bcs'] - 1)  # ajustar a 0–4

X = np.array(images)
y_weight = np.array(weights)
y_bcs = np.array(bcs)

# División train-test
X_train, X_test, y_weight_train, y_weight_test, y_bcs_train, y_bcs_test = train_test_split(
    X, y_weight, y_bcs, test_size=0.2, random_state=42
)

# Modelo
base_model = MobileNetV2(
    input_shape=(IMG_SIZE, IMG_SIZE, 3),
    include_top=False,
    weights='imagenet'
)

base_model.trainable = False

inputs = tf.keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3))
x = base_model(inputs, training=False)
x = layers.GlobalAveragePooling2D()(x)
x = layers.Dense(256, activation='relu')(x)
x = layers.Dropout(0.5)(x)

weight_output = layers.Dense(1, activation='linear', name='weight')(x)
bcs_output = layers.Dense(5, activation='softmax', name='bcs')(x)

model = models.Model(inputs=inputs, outputs=[weight_output, bcs_output])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss={
        'weight': 'mse',
        'bcs': 'sparse_categorical_crossentropy'
    },
    metrics={
        'weight': ['mae'],
        'bcs': ['accuracy']
    }
)

model.fit(
    X_train,
    {'weight': y_weight_train, 'bcs': y_bcs_train},
    validation_split=0.2,
    epochs=50,
    batch_size=8
)

model.save("../backend/model/modelo_ganado.h5")