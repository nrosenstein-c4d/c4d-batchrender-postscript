# jump-to: 9, 23
from shlex import split
from subprocess import Popen

command = 'shutdown /s'
command = split(command)

def main():
    p = Popen(command)

