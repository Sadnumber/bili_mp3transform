import os
import shutil


def find_and_copy_files(start_dir, target_dir, search_pattern):
    """
    遍历start_dir目录及其子目录，查找文件名中包含search_pattern的.m4s文件，
    并将它们复制到target_dir目录中。

    :param start_dir: 起始目录的路径
    :param target_dir: 目标目录的路径
    :param search_pattern: 要搜索的文件名中的模式
    """
    # 确保目标目录存在，如果不存在则创建它
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

        # 遍历目录及其子目录
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            # 检查文件名是否包含指定模式和是否为.m4s文件
            if search_pattern in file and file.endswith('.m4s'):
                # 构建文件的完整路径
                source_path = os.path.join(root, file)
                # 构建目标文件的路径
                # 这里简单地将文件名添加到目标目录中，你也可以根据需要添加更复杂的命名规则
                dest_path = os.path.join(target_dir, file)
                # 复制文件
                shutil.copy(source_path, dest_path)
                print(f"已复制 {source_path} 到 {dest_path}")

            # 示例用法
def remove_leading_zeros(file_path, file_path1):
    # 读取文件内容
    with open(file_path, 'rb') as file:
        data = file.read()

    # 找到需要去除的部分
    if data.startswith(b'000000000'):
        data = data[9:]  # 删除前9个"0"

    # 将修改后的内容写回文件
    with open(file_path1, 'wb') as file:
        file.write(data)

if __name__ == "__main__":
    start_directory = 'D:/RuanYancheng/Videos/bilibili'  # 替换为你的起始目录路径
    target_directory = 'D:/m4smp3/m4s'  # 替换为你的目标目录路径
    search_pattern = '-30280'  # 你要搜索的文件名中的模式
    find_and_copy_files(start_directory, target_directory, search_pattern)

