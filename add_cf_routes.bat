@echo off
echo Adding routes to Cloudflare Edge via Wi-Fi gateway...
route add 198.41.192.0 mask 255.255.255.0 192.168.0.1 if 9
route add 198.41.200.0 mask 255.255.255.0 192.168.0.1 if 9
echo Done. Verifying...
route print 198.41.*
pause
