#!/usr/bin/env python3
"""Execute a command with dotenv values without evaluating shell code."""

import argparse
import os
from pathlib import Path
import sys

import environ


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Executa um comando carregando um arquivo dotenv com segurança.'
    )
    parser.add_argument('--env-file', default='.env', type=Path, help='Arquivo dotenv.')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='Comando após --.')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        parser.error('informe um comando após --')
    if not args.env_file.is_file():
        parser.error(f'arquivo dotenv não encontrado: {args.env_file}')

    environ.Env.read_env(args.env_file, overwrite=False)
    try:
        # Execução direta, sem shell; o comando é a interface explícita deste wrapper.
        os.execvpe(command[0], command, os.environ.copy())  # nosec B606
    except FileNotFoundError:
        print(f'comando não encontrado: {command[0]}', file=sys.stderr)
        return 127
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
