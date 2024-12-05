import os
import subprocess
import datetime
from shutil import rmtree, move
from colorama import Fore, Style


def parse_git_log(git_after, repo_path):
    """Получение лога изменений из Git."""
    git_params = ["git", "log", "--after", git_after, "--pretty=%s (%cn)", "--name-only", "--no-merges"]
    try:
        result = subprocess.run(git_params, cwd=repo_path, stdout=subprocess.PIPE, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды git: {e}")
        return []


def generate_logs(content, now_str):
    """Создание логов с названиями коммитов и родительскими папками изменений."""
    if not content:
        print("Нет данных для создания логов.")
        return []

    log_lines = []
    all_lines = []
    affected_files = []
    parent_folders = {}

    for line in content:
        if len(line.strip()) == 0:
            continue

        if not line.startswith(" "):  # Это заголовок коммита
            commit_message = line
            parent_folders[commit_message] = set()  # Храним уникальные родительские папки
        elif line.startswith("addons/"):  # Это путь, связанный с коммитом
            parent_folder = line.split("/")[1]  # Извлекаем родительскую папку
            if commit_message in parent_folders:
                parent_folders[commit_message].add(parent_folder)
                if parent_folder not in affected_files:
                    affected_files.append(parent_folder)

    # Создаем файл с коротким списком изменений
    short_file_path = f"changelog_{now_str}_short.txt"
    try:
        with open(short_file_path, "w", encoding="utf8") as f:
            for commit, folders in parent_folders.items():
                folder_list = ", ".join(sorted(folders))
                f.write(f"* [ ] {folder_list}: {commit}\n")
        print(f"Файл кратких изменений сохранен в {short_file_path}.")
    except Exception as e:
        print(f"Ошибка при записи файла {short_file_path}: {e}")

    return affected_files
def get_deleted_folders(git_after, repo_path):
    """Получение списка удаленных папок из Git."""
    git_params = ["git", "log", "--after", git_after, "--diff-filter=D", "--name-only", "--no-merges"]
    try:
        result = subprocess.run(git_params, cwd=repo_path, stdout=subprocess.PIPE, text=True, check=True)
        deleted_items = result.stdout.splitlines()

        # Оставляем только директории
        deleted_folders = [
            item for item in deleted_items if os.path.dirname(item) and item.endswith("/")
        ]
        return deleted_folders
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды git: {e}")
        return []


def save_deleted_folders(deleted_folders, now_str):
    """Сохраняет список удаленных папок в файл."""
    file_name = f"delete_file_{now_str}.txt"
    try:
        with open(file_name, "w", encoding="utf8") as f:
            f.write("\n".join(deleted_folders))
        print(f"Список удаленных папок сохранен в {file_name}.")
    except Exception as e:
        print(f"Ошибка при записи файла {file_name}: {e}")

def clean_symlinks(custom_addons_folder, protected_folders, affected_files):
    """
    Очистка устаревших папок и Junction ссылок в custom_addons_folder,
    удаляя устаревшие, не входящие в список affected_files, за исключением защищенных папок.
    """
    print(f"Очистка папок и Junction ссылок в {custom_addons_folder}...")

    for folder in os.listdir(custom_addons_folder):
        folder_path = os.path.join(custom_addons_folder, folder)

        # Пропускаем защищенные папки
        if folder in protected_folders:
            print(f"Пропуск защищенной папки: {folder_path}")
            continue

        # Удаляем папки или Junction, если они не в списке affected_files
        if folder not in affected_files:
            try:
                print(f"Удаление устаревшей папки или Junction: {folder_path}")
                if os.path.islink(folder_path) or (os.path.isdir(folder_path) and not os.path.ismount(folder_path)):
                    # Удаляем Junction или символическую ссылку
                    os.unlink(folder_path)
                elif os.path.isdir(folder_path):
                    # Удаляем обычную директорию
                    rmtree(folder_path)
                else:
                    print(f"{folder_path} не является ссылкой или папкой. Пропуск.")
            except Exception as e:
                print(f"Ошибка при удалении {folder_path}: {e}")


def create_symlinks(affected_files, now_str, do_copy, custom_addons_folder, repo_path):
    """Создание Junction Points для измененных папок."""
    if not do_copy:
        print("Пропущено создание символических ссылок из-за флага -nc")
        return

    protected_folders = ["mkk_sys"]
    clean_symlinks(custom_addons_folder, protected_folders, affected_files)

    # Путь к папке addons относительно repo_path
    addons_dir = os.path.join(repo_path, "addons")
    release_path = os.path.join(os.getcwd(), custom_addons_folder)
    os.makedirs(release_path, exist_ok=True)

    print("\nСписок всех папок в 'addons/':")
    for folder in os.listdir(addons_dir):
        folder_path = os.path.join(addons_dir, folder)
        if os.path.isdir(folder_path):
            print(f"  {folder}")

    for file in set(affected_files):
        addon_dir = os.path.join(addons_dir, file)
        symlink_path = os.path.join(release_path, file)

        print(f"\nПроверка папки: {addon_dir}")
        if not os.path.exists(addon_dir):
            print(f"Папка {addon_dir} не найдена, пропускаем создание Junction.")
            continue

        try:
            if os.path.exists(symlink_path):
                print(f"Удаление существующей ссылки: {symlink_path}")
                if os.path.islink(symlink_path) or os.path.isdir(symlink_path) and not os.path.ismount(symlink_path):
                    os.unlink(symlink_path)  # Удаляем Junction или символическую ссылку
                else:
                    rmtree(symlink_path)  # Удаляем папку

            os.system(f'mklink /J "{symlink_path}" "{addon_dir}"')
            print(f"Junction создан для {addon_dir} в папке {release_path}")
        except Exception as e:
            print(f"Ошибка при создании Junction для {file}: {e}")
    input("\nНажмите Enter для продолжения после создания Junction...")


def run_hemtt(custom_hemtt_path):
    r"""Запуск команды `.\tools\hemtt.exe release` из кастомного места."""
    try:
        os.chdir(custom_hemtt_path)
        hemtt_path = os.path.join(custom_hemtt_path, "tools", "hemtt.exe")
        subprocess.run([hemtt_path, "release"], check=True)
        print("Команда 'hemtt release' успешно выполнена.")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении hemtt.exe: {e}")
    except FileNotFoundError as e:
        print(f"Файл hemtt.exe не найден: {e}")
    input("\nНажмите Enter для продолжения после выполнения hemtt.exe...")


def find_obfuscation_folders(addons_folder):
    """Определяет папки для обфускации на основе config.cpp."""
    obfuscation_folders = []
    for folder in os.listdir(addons_folder):
        folder_path = os.path.join(addons_folder, folder)
        if not os.path.isdir(folder_path):
            continue

        config_path = os.path.join(folder_path, "config.cpp")
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf8") as f:
                    if "mkk_shield=1" in f.read():
                        obfuscation_folders.append(folder)
                        print(f"Добавлена папка для обфускации: {folder}")
            except Exception as e:
                print(f"Ошибка при чтении файла {config_path}: {e}")
    return obfuscation_folders


def obfuscate_files_with_shortcut(makepbo_shortcut, obfuscation_folders, addons_folder, target_folder):
    """Обфускация файлов через MakePbo."""
    for folder in obfuscation_folders:
        folder_path = os.path.join(addons_folder, folder)
        if not os.path.isdir(folder_path):
            print(f"Ошибка: Папка {folder_path} не найдена.")
            continue

        print(f"Запуск обфускации для папки: {folder_path}")
        try:
            subprocess.run(["cmd", "/c", makepbo_shortcut, folder_path], check=True, shell=True)
            pbo_file_name = f"{folder}.pbo"
            source_pbo_path = os.path.join(addons_folder, pbo_file_name)

            if os.path.isfile(source_pbo_path):
                target_pbo_path = os.path.join(target_folder, pbo_file_name)
                move(source_pbo_path, target_pbo_path)
                print(f".pbo файл {pbo_file_name} перемещен в {target_folder}")
            else:
                print(f"Ошибка: .pbo файл {pbo_file_name} не найден после обфускации.")
        except Exception as e:
            print(f"Ошибка при обфускации папки {folder_path}: {e}")


def main():
    repo_path = "F:\\Arma3\\github\\MKK-MODES"
    custom_addons_folder = "F:\\Arma3\\Realese\\addons"
    custom_hemtt_path = "F:\\Arma3\\Realese"
    custom_makepbo_shortcut = "F:\\Arma3\\Realese\\tools\\MakePbo2.lnk"
    target_folder = "F:\\Arma3\\Realese\\.hemttout\\release\\addons"

    now = datetime.datetime.now().strftime("%Y-%m-%d")
    git_after = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    do_copy = True

    print(f"Запуск с датой: {git_after}, создание символических ссылок: {'включено' if do_copy else 'выключено'}")

    git_log = parse_git_log(git_after, repo_path)
    if not git_log:
        print("Лог изменений пуст или недоступен.")
        return

    # Новый функционал: Получение и сохранение списка удаленных папок
    deleted_folders = get_deleted_folders(git_after, repo_path)
    if deleted_folders:
        save_deleted_folders(deleted_folders, now)

    affected_files = generate_logs(git_log, now)
    if affected_files:
        create_symlinks(affected_files, now, do_copy, custom_addons_folder, repo_path)
        run_hemtt(custom_hemtt_path)

    obfuscation_folders = find_obfuscation_folders(custom_addons_folder)
    if obfuscation_folders:
        obfuscate_files_with_shortcut(custom_makepbo_shortcut, obfuscation_folders, custom_addons_folder, target_folder)

    print(Fore.GREEN + "РЕЛИЗ ПОДГОТОВЛЕН" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
