#!/usr/bin/env python3
import argparse
import sys
import requests
import json
from urllib.parse import urljoin

class DependencyFetcher:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_package_dependencies(self, package_name, version):
        """Получает прямые зависимости пакета"""
        try:
            # Получаем информацию о пакете
            package_url = f"{self.base_url}{package_name.lower()}/index.json"
            response = self.session.get(package_url)
            response.raise_for_status()
            
            package_data = response.json()
            
            #Поиск нужной версии
            for version_entry in package_data.get('versions', []):
                if version_entry['version'] == version:
                    # Получаем детали версии
                    version_url = version_entry['@id']
                    version_response = self.session.get(version_url)
                    version_response.raise_for_status()
                    
                    version_data = version_response.json()
                    return self._extract_dependencies(version_data)
            
            raise ValueError(f"Версия {version} не найдена для пакета {package_name}")
            
        except requests.RequestException as e:
            raise Exception(f"Ошибка сети: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Ошибка парсинга JSON: {e}")
    
    def _extract_dependencies(self, version_data):
        """Извлекает зависимости из данных версии"""
        dependencies = []
        
        #Поиск зависимости в catalogEntry
        catalog_entry = version_data.get('catalogEntry', {})
        dependency_groups = catalog_entry.get('dependencyGroups', [])
        
        for group in dependency_groups:
            for dep in group.get('dependencies', []):
                dependencies.append({
                    'id': dep['id'],
                    'version_range': dep.get('range', '')
                })
        
        return dependencies

class Config:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Dependency Graph Visualizer')
        self._setup_arguments()
        self.args = None
    
    def _setup_arguments(self):
        # Параметры из этапа 1
        self.parser.add_argument('--package', required=True, help='Имя анализируемого пакета')
        self.parser.add_argument('--source', required=True, help='URL репозитория или путь к файлу')
        self.parser.add_argument('--test-mode', action='store_true', help='Режим тестового репозитория')
        self.parser.add_argument('--version', required=True, help='Версия пакета')
        self.parser.add_argument('--ascii-tree', action='store_true', help='Вывод в формате ASCII-дерева')
        self.parser.add_argument('--max-depth', type=int, default=10, help='Максимальная глубина анализа')
        self.parser.add_argument('--filter', help='Подстрока для фильтрации пакетов')
    
    def parse_args(self):
        try:
            self.args = self.parser.parse_args()
            self._validate_args()
            return self.args
        except Exception as e:
            print(f"Ошибка: {e}")
            sys.exit(1)
    
    def _validate_args(self):
        if self.args.max_depth <= 0:
            raise ValueError("Максимальная глубина должна быть положительным числом")
        if not self.args.version:
            raise ValueError("Версия пакета не может быть пустой")

def main():
    config = Config()
    args = config.parse_args()
    
    # Вывод параметров
    print("Параметры конфигурации:")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    
    print("\n" + "="*50)
    
    # Этап 2: Получение зависимостей
    if not args.test_mode:
        try:
            print(f"Получение зависимостей для {args.package} версии {args.version}...")
            
            # Используем официальный NuGet репозиторий
            fetcher = DependencyFetcher("https://api.nuget.org/v3/registration5-gz-semver2/")
            dependencies = fetcher.get_package_dependencies(args.package, args.version)
            
            # Вывод прямых зависимостей
            print(f"\nПрямые зависимости пакета {args.package} {args.version}:")
            if dependencies:
                for dep in dependencies:
                    print(f"  - {dep['id']} {dep['version_range']}")
            else:
                print("  Зависимости не найдены")
                
        except Exception as e:
            print(f"Ошибка при получении зависимостей: {e}")
    else:
        print("Режим тестирования - пропуск получения зависимостей")

if __name__ == "__main__":
    main()