#!/usr/bin/env python3
"""
Тесты для проверки работы программы получения зависимостей NuGet пакетов
"""
import subprocess
import sys
import json

def run_command(args):
    """Запускает программу с указанными аргументами и возвращает результат"""
    cmd = [sys.executable, "src/main.py"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return result.returncode, result.stdout or "", result.stderr or ""
    except Exception as e:
        return 1, "", str(e)

def test_basic_functionality():
    """Тест базовой функциональности - получение зависимостей для Newtonsoft.Json"""
    print("Тест 1: Базовая функциональность (Newtonsoft.Json 13.0.1)")
    print("-" * 60)
    
    returncode, stdout, stderr = run_command([
        "--package", "Newtonsoft.Json",
        "--version", "13.0.1",
        "--source", "https://api.nuget.org/v3/index.json"
    ])
    
    if returncode != 0:
        print(f"ОШИБКА: программа завершилась с кодом {returncode}")
        if stderr:
            print(f"Stderr: {stderr}")
        return False
    
    # Проверяем, что вывод содержит зависимости
    if "Прямые зависимости" in stdout:
        if "Microsoft.CSharp" in stdout:
            print("OK: Тест пройден: зависимости найдены")
            return True
        else:
            print("ПРЕДУПРЕЖДЕНИЕ: Зависимости не найдены в выводе")
            return False
    else:
        print("ОШИБКА: не найдено 'Прямые зависимости' в выводе")
        return False

def test_package_not_found():
    """Тест обработки несуществующего пакета"""
    print("\nТест 2: Обработка несуществующего пакета")
    print("-" * 60)
    
    returncode, stdout, stderr = run_command([
        "--package", "NonExistentPackage12345",
        "--version", "1.0.0",
        "--source", "https://api.nuget.org/v3/index.json"
    ])
    
    if "Ошибка" in stdout or "Ошибка" in stderr:
        print("OK: Тест пройден: ошибка корректно обработана")
        return True
    else:
        print("ПРЕДУПРЕЖДЕНИЕ: Ошибка не была обработана")
        return False

def test_version_not_found():
    """Тест обработки несуществующей версии"""
    print("\nТест 3: Обработка несуществующей версии")
    print("-" * 60)
    
    returncode, stdout, stderr = run_command([
        "--package", "Newtonsoft.Json",
        "--version", "999.999.999",
        "--source", "https://api.nuget.org/v3/index.json"
    ])
    
    if "не найдена" in stdout or "не найдена" in stderr:
        print("OK: Тест пройден: несуществующая версия корректно обработана")
        return True
    else:
        print("ПРЕДУПРЕЖДЕНИЕ: Ошибка не была обработана корректно")
        return False

def test_no_dependencies():
    """Тест пакета без зависимостей"""
    print("\nТест 4: Пакет без зависимостей")
    print("-" * 60)
    
    # Попробуем простой пакет, который обычно не имеет зависимостей
    returncode, stdout, stderr = run_command([
        "--package", "System.Runtime.CompilerServices.Unsafe",
        "--version", "6.0.0",
        "--source", "https://api.nuget.org/v3/index.json"
    ])
    
    if returncode == 0:
        if "Зависимости не найдены" in stdout or "Прямые зависимости" in stdout:
            print("OK: Тест пройден: пакет без зависимостей обработан")
            return True
        else:
            print("ПРЕДУПРЕЖДЕНИЕ: Неожиданный вывод")
            return False
    else:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Ошибка при выполнении: {stderr}")
        return False

def test_duplicate_removal():
    """Тест проверки удаления дубликатов"""
    print("\nТест 5: Проверка удаления дубликатов зависимостей")
    print("-" * 60)
    
    returncode, stdout, stderr = run_command([
        "--package", "Newtonsoft.Json",
        "--version", "13.0.1",
        "--source", "https://api.nuget.org/v3/index.json"
    ])
    
    if returncode == 0:
        # Подсчитываем вхождения Microsoft.CSharp
        count = stdout.count("Microsoft.CSharp")
        if count <= 1:
            print("OK: Тест пройден: дубликаты удалены")
            return True
        else:
            print(f"ОШИБКА: Найдены дубликаты: Microsoft.CSharp встречается {count} раз(а)")
            return False
    else:
        print(f"ОШИБКА: Ошибка при выполнении: {stderr}")
        return False

def main():
    """Запуск всех тестов"""
    print("=" * 60)
    print("Запуск тестов для Dependency Fetcher")
    print("=" * 60)
    
    tests = [
        test_basic_functionality,
        test_duplicate_removal,
        test_package_not_found,
        test_version_not_found,
        test_no_dependencies,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"ОШИБКА в тесте: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("Результаты тестирования:")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("Все тесты пройдены успешно!")
        return 0
    else:
        print(f"Не пройдено тестов: {total - passed}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

