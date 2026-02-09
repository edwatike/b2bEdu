@echo off
echo Disabling happ-tun VPN adapter...
netsh interface set interface "happ-tun" admin=disable
echo Done. Adapter status:
netsh interface show interface "happ-tun"
pause
