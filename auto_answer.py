import subprocess
import time
import sys

# Запускаем лаунчер
process = subprocess.Popen(
    ["d:\\b2b\\B2BLauncher.exe", "--mode", "production"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

# Ждем вопроса про VPN и отвечаем "y"
time.sleep(3)
process.stdin.write("y\n")
process.stdin.flush()

# Читаем вывод
while True:
    output = process.stdout.readline()
    if output == '' and process.poll() is not None:
        break
    if output:
        print(output.strip())

# Закрываем
process.stdin.close()
process.stdout.close()
process.stderr.close()
process.wait()
