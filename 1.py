import os
import shutil
import random

def split_and_move_files(src_folder, dest_folder, train_ratio=0.7, test_ratio=0.2, valid_ratio=0.1):
    """
    将文件夹中的文件按比例随机分配到 train、test 和 valid 文件夹中。
    
    :param src_folder: 源文件夹路径
    :param dest_folder: 目标文件夹路径
    :param train_ratio: 训练集比例
    :param test_ratio: 测试集比例
    :param valid_ratio: 验证集比例
    """
    # 检查比例是否正确
    assert abs(train_ratio + test_ratio + valid_ratio - 1.0) < 1e-6, "比例之和必须等于 1"

    # 确保目标文件夹中的子文件夹存在
    train_folder = os.path.join(dest_folder, "train")
    test_folder = os.path.join(dest_folder, "test")
    valid_folder = os.path.join(dest_folder, "valid")
    os.makedirs(train_folder, exist_ok=True)
    os.makedirs(test_folder, exist_ok=True)
    os.makedirs(valid_folder, exist_ok=True)

    # 获取所有文件的完整路径
    all_files = []
    for root, _, files in os.walk(src_folder):
        for file in files:
            all_files.append(os.path.join(root, file))

    # 打乱文件顺序
    random.shuffle(all_files)

    # 按比例分配
    total_files = len(all_files)
    train_split = int(total_files * train_ratio)
    test_split = int(total_files * (train_ratio + test_ratio))

    train_files = all_files[:train_split]
    test_files = all_files[train_split:test_split]
    valid_files = all_files[test_split:]

    # 定义文件移动函数
    def move_files(file_list, target_folder):
        for file_path in file_list:
            # 获取文件名
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(target_folder, file_name)

            # 如果目标文件夹中已存在同名文件，解决冲突
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(file_name)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(target_folder, f"{base}_{counter}{ext}")
                    counter += 1
            
            shutil.move(file_path, dest_path)

    # 移动文件
    move_files(train_files, train_folder)
    move_files(test_files, test_folder)
    move_files(valid_files, valid_folder)

    print(f"总文件数: {total_files}")
    print(f"训练集: {len(train_files)} 文件 -> {train_folder}")
    print(f"测试集: {len(test_files)} 文件 -> {test_folder}")
    print(f"验证集: {len(valid_files)} 文件 -> {valid_folder}")

# 示例用法
src_folder = "lpd_5"  # 替换为源文件夹路径
dest_folder = "dataset/lpd5"  # 替换为目标文件夹路径

split_and_move_files(src_folder, dest_folder)