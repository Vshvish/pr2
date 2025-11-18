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
            
            # NuGet API v3 использует вложенную структуру items
            # Обходим все элементы items, включая пагинацию
            items = package_data.get('items', [])
            pages_to_check = []
            
            for item in items:
                # Каждый item может содержать items с версиями или ссылку на другую страницу
                version_items = item.get('items', [])
                
                if version_items:
                    # Ищем нужную версию во вложенных items
                    for version_entry in version_items:
                        catalog_entry = version_entry.get('catalogEntry', {})
                        if catalog_entry.get('version') == version:
                            # Если данные версии уже есть в entry, используем их
                            if 'catalogEntry' in version_entry:
                                cat_entry = version_entry['catalogEntry']
                                if 'dependencyGroups' in cat_entry:
                                    return self._extract_dependencies(version_entry)
                            
                            # Иначе получаем детали версии по ссылке
                            version_url = version_entry.get('@id')
                            if version_url:
                                version_response = self.session.get(version_url)
                                version_response.raise_for_status()
                                version_data = version_response.json()
                                return self._extract_dependencies(version_data)
                else:
                    # Если нет вложенных items, это может быть ссылка на страницу
                    # или листовая версия
                    if 'catalogEntry' in item:
                        catalog_entry = item['catalogEntry']
                        if catalog_entry.get('version') == version:
                            return self._extract_dependencies(item)
                    # Сохраняем ссылку на страницу для последующей проверки
                    item_url = item.get('@id')
                    if item_url:
                        pages_to_check.append(item_url)
            
            # Проверяем дополнительные страницы (пагинация)
            for page_url in pages_to_check:
                page_response = self.session.get(page_url)
                page_response.raise_for_status()
                page_data = page_response.json()
                
                page_items = page_data.get('items', [])
                for version_entry in page_items:
                    catalog_entry = version_entry.get('catalogEntry', {})
                    if catalog_entry.get('version') == version:
                        # Если данные версии уже есть в entry, используем их
                        if 'catalogEntry' in version_entry:
                            cat_entry = version_entry['catalogEntry']
                            if 'dependencyGroups' in cat_entry:
                                return self._extract_dependencies(version_entry)
                        
                        # Иначе получаем детали версии по ссылке
                        version_url = version_entry.get('@id')
                        if version_url:
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
        seen_ids = set()  # Для отслеживания уже добавленных зависимостей
        
        # Ищем зависимости в catalogEntry
        catalog_entry = version_data.get('catalogEntry', {})
        if not catalog_entry and isinstance(version_data, dict):
            # Если catalogEntry нет на верхнем уровне, возможно это прямая структура
            catalog_entry = version_data
        
        dependency_groups = catalog_entry.get('dependencyGroups', [])
        
        for group in dependency_groups:
            for dep in group.get('dependencies', []):
                dep_id = dep['id']
                # Добавляем только уникальные зависимости
                if dep_id not in seen_ids:
                    seen_ids.add(dep_id)
                    dependencies.append({
                        'id': dep_id,
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
    
    # Вывод параметров (этап 1)
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
            
            # Вывод прямых зависимостей (требование этапа 2)
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