param(
    [Parameter(Mandatory = $false)]
    [string]$BaseUrl
)

$ErrorActionPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    exit 0
}

$base = $BaseUrl.Trim().Trim('"')
if ([string]::IsNullOrWhiteSpace($base)) {
    exit 0
}

$paths = @('/healthz', '/health', '/')
foreach ($p in $paths) {
    try {
        $u = $base.TrimEnd('/') + $p
        $r = Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 3 -Method GET
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
            exit 0
        }
    }
    catch {
        # ignore
    }
}

try {
    $uri = [Uri]$base
    $port = $uri.Port
    if ($port -le 0) {
        $port = if ($uri.Scheme -eq 'https') { 443 } else { 80 }
    }

    $tcp = Test-NetConnection -ComputerName $uri.Host -Port $port -WarningAction SilentlyContinue
    if ($tcp.TcpTestSucceeded) {
        exit 0
    }
}
catch {
    # ignore
}

exit 1
