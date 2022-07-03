from io import BytesIO
from os import remove
from time import time
import tensorflow as tf
from PIL import Image
from requests import get

# 模型文件夹路径
model_save_dir = "./data/model"
image_size = 64
model = tf.keras.models.Sequential(
    [
        # 卷积、池化、卷积、池化...
        tf.keras.layers.Conv2D(16, (3, 3), activation="relu", input_shape=(64, 64, 3)),
        tf.keras.layers.MaxPooling2D(2, 2),
        tf.keras.layers.Conv2D(32, (3, 3), activation="relu"),
        tf.keras.layers.MaxPooling2D(2, 2),
        tf.keras.layers.Conv2D(64, (3, 3), activation="relu"),
        tf.keras.layers.MaxPooling2D(2, 2),
        # 为全连接层准备
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(128, activation="relu"),
        # 二分类故使用sigmoid
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ]
)
# 复现已保存的模型
checkpoint = tf.train.Checkpoint(
    myModel=model, myOptimizer=tf.keras.optimizers.Adam(0.001)
)
model.compile(
    loss="binary_crossentropy",  # 损失函数设定为binary_crossentropy
    optimizer=tf.keras.optimizers.Adam(0.001),  # 采用Adam优化器
    metrics=["acc"],
)  # 关注准确率指标
checkpoint.restore(tf.train.latest_checkpoint(model_save_dir))


def is_Capoo(pic_path, from_url=False):
    """
    输入图片，判断是否为猫猫虫

    （图片支持png/jpeg/gif/bmp/webp格式）

    :param pic_path: 图片路径(本地路径或url)
    :param path_type: "u"或"l"，分别代表url和local
    :return: 数值，0或1或2
    0表示应该是猫猫虫；
    1表示应该是蜜桃猫；
    2表示异常
    """
    path = f"./data/meme_{int(time())}.png"
    if from_url:
        r = get(pic_path)
        img = Image.open(BytesIO(r.content))
        img.save(path)
    else:
        img = Image.open(pic_path)
        img.save(path)
    image_raw_data = tf.io.gfile.GFile(
        path, "rb"
    ).read()  # 先获取原始数据
    remove(path)  # 删除临时文件
    image_tensor = tf.image.decode_png(image_raw_data, channels=3)  # 将图片原始数据转化成三维张量
    img_resized = tf.image.resize(
        image_tensor, [image_size, image_size]
    )  # 将三维张量调整到[64,64,3]的格式
    final = tf.expand_dims(img_resized, 0)  # 将三维张量调整为CNN输入需要的[None,64,64,3]的格式

    result = model.predict(final)
    # 返回[[0.]]说明是猫猫虫，返回[[1.]]说明不是，只能做二分类

    if result[0][0] == 0:
        return 0
    elif result[0][0] == 1:
        return 1
    else:
        return 2

if __name__ == '__main__':
    print(['Is Capoo', 'Not Capoo', 'Error!'][is_Capoo('https://img.stickers.cloud/packs/7a2b50a5-057e-4f9d-8a10-9e69df509c0a/png/ad6f15c9-9f49-4af3-a742-7364dfc3283f.png', True)])

