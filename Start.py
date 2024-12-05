import os
import subprocess
import datetime
from shutil import rmtree, move
from colorama import Fore, Style


def find_changed_folders(repo_path, days):
    """
    Определяет измененные папки в репозитории за последние 'days' дней.
    """
    git_after = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    git_params = ["git", "log", "--after", git_after, "--name-only", "--no-merges"]
    try:
        result = subprocess.run(git_params, cwd=repo_path, stdout=subprocess.PIPE, text=True, check=True)
        changed_files = result.stdout.splitlines()

        # Извлекаем уникальные измененные папки
        changed_folders = set()
        for file_path in changed_files:
            if file_path.startswith("addons/"):
                folder = file_path.split("/")[1]
                changed_folders.add(folder)

        print(f"Измененные папки за последние {days} дней: {changed_folders}")
        return list(changed_folders)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды git: {e}")
        return []


def clean_symlinks(custom_addons_folder, protected_folders):
    """
    Очистка устаревших папок и Junction ссылок в custom_addons_folder,
    за исключением защищенных папок.
    """
    print(f"Очистка папок и Junction ссылок в {custom_addons_folder}...")

    for folder in os.listdir(custom_addons_folder):
        folder_path = os.path.join(custom_addons_folder, folder)

        # Пропускаем защищенные папки
        if folder in protected_folders:
            print(f"Пропуск защищенной папки: {folder_path}")
            continue

        # Удаляем папки или Junction
        try:
            print(f"Удаление папки или Junction: {folder_path}")
            if os.path.islink(folder_path) or (os.path.isdir(folder_path) and not os.path.ismount(folder_path)):
                os.unlink(folder_path)  # Удаляем Junction или символическую ссылку
            elif os.path.isdir(folder_path):
                rmtree(folder_path)  # Удаляем папку
            else:
                print(f"{folder_path} не является ссылкой или папкой. Пропуск.")
        except Exception as e:
            print(f"Ошибка при удалении {folder_path}: {e}")


def create_symlinks(changed_folders, do_copy, custom_addons_folder, repo_path):
    """Создание Junction Points для измененных папок."""
    if not do_copy:
        print("Пропущено создание символических ссылок из-за флага -nc")
        return

    protected_folders = ["mkk_sys"]
    clean_symlinks(custom_addons_folder, protected_folders)

    # Путь к папке addons относительно repo_path
    addons_dir = os.path.join(repo_path, "addons")
    release_path = os.path.join(os.getcwd(), custom_addons_folder)
    os.makedirs(release_path, exist_ok=True)

    print("\nСписок измененных папок в 'addons/':")
    for folder in changed_folders:
        folder_path = os.path.join(addons_dir, folder)
        if os.path.isdir(folder_path):
            print(f"  {folder}")

            # Создаем Junction для каждой измененной папки
            addon_dir = os.path.join(addons_dir, folder)
            symlink_path = os.path.join(release_path, folder)

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
                print(f"Ошибка при создании Junction для {folder}: {e}")
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
    days = 2  # Задайте количество дней для сканирования изменений

    # Найти измененные папки за последние N дней
    changed_folders = find_changed_folders(repo_path, days)

    do_copy = True

    print(f"Создание символических ссылок: {'включено' if do_copy else 'выключено'}")

    create_symlinks(changed_folders, do_copy, custom_addons_folder, repo_path)
    run_hemtt(custom_hemtt_path)

    obfuscation_folders = find_obfuscation_folders(custom_addons_folder)
    if obfuscation_folders:
        obfuscate_files_with_shortcut(custom_makepbo_shortcut, obfuscation_folders, custom_addons_folder, target_folder)

    print(Fore.GREEN + "РЕЛИЗ ПОДГОТОВЛЕН" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
