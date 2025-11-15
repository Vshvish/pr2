#!/usr/bin/env python3
import argparse
import sys

class Config:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Dependency Graph Visualizer')
        self._setup_arguments()
        self.args = None
    
    def _setup_arguments(self):
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
        # Проверка максимальной глубины
        if self.args.max_depth <= 0:
            raise ValueError("Максимальная глубина должна быть положительным числом")
        
        # Проверка версии
        if not self.args.version:
            raise ValueError("Версия пакета не может быть пустой")

def main():
    config = Config()
    args = config.parse_args()
    
    # Вывод всех параметров
    print("Параметры конфигурации:")
    for key, value in vars(args).items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()