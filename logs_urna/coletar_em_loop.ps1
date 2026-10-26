# Mantém o coletor de logs rodando: se ele parar (erro, queda de rede), reinicia em 30 s. Ctrl-C duas vezes encerra.
# Os argumentos são repassados ao coletor, por exemplo: .\coletar_em_loop.ps1 --workers 12 --max-rate 8
Set-Location $PSScriptRoot
while ($true) {
    & python -u coletar_logs.py @args
    Write-Host "[$(Get-Date -Format HH:mm:ss)] coletor saiu (código $LASTEXITCODE); reiniciando em 30 s..."
    Start-Sleep -Seconds 30
}
