"""DNS record generation and live verification helpers."""
import base64
import dns.resolver
from typing import Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_dkim_keypair(bits: int = 2048) -> tuple[str, str]:
    """Generate an RSA keypair for DKIM. Returns (private_pem, public_b64)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_b64 = base64.b64encode(pub).decode("ascii")
    return private_pem, public_b64


def generate_dns_records(domain: str, dkim_selector: str, dkim_public_b64: str,
                         mail_host: str = "mail") -> list[dict]:
    """Return the canonical DNS record set this platform expects on a domain."""
    fqdn_mail = f"{mail_host}.{domain}"
    return [
        {
            "kind": "MX",
            "host": f"{domain}.",
            "name": "@",
            "value": f"10 {fqdn_mail}.",
            "ttl": 3600,
            "description": "Primary mail exchanger",
        },
        {
            "kind": "SPF",
            "host": f"{domain}.",
            "name": "@",
            "value": "v=spf1 mx ~all",
            "ttl": 3600,
            "description": "Sender Policy Framework (TXT record)",
        },
        {
            "kind": "DKIM",
            "host": f"{dkim_selector}._domainkey.{domain}.",
            "name": f"{dkim_selector}._domainkey",
            "value": f"v=DKIM1; k=rsa; p={dkim_public_b64}",
            "ttl": 3600,
            "description": "DomainKeys Identified Mail public key (TXT record)",
        },
        {
            "kind": "DMARC",
            "host": f"_dmarc.{domain}.",
            "name": "_dmarc",
            "value": f"v=DMARC1; p=quarantine; rua=mailto:postmaster@{domain}; adkim=s; aspf=s",
            "ttl": 3600,
            "description": "Domain-based Message Authentication (TXT record)",
        },
        {
            "kind": "A",
            "host": f"{fqdn_mail}.",
            "name": mail_host,
            "value": "<your-server-ip>",
            "ttl": 3600,
            "description": "A record pointing the mail hostname to your server",
        },
    ]


def _resolve_txt(name: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 4.0
    resolver.timeout = 2.0
    try:
        answers = resolver.resolve(name, "TXT")
    except Exception:
        return []
    results = []
    for r in answers:
        try:
            parts = [b.decode("utf-8", errors="ignore") if isinstance(b, bytes) else str(b) for b in r.strings]
            results.append("".join(parts))
        except Exception:
            results.append(str(r))
    return results


def _resolve_mx(name: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 4.0
    resolver.timeout = 2.0
    try:
        answers = resolver.resolve(name, "MX")
    except Exception:
        return []
    return [f"{a.preference} {a.exchange.to_text()}" for a in answers]


def check_spf(domain: str) -> dict:
    records = _resolve_txt(domain)
    spf = next((r for r in records if r.lower().startswith("v=spf1")), None)
    return {"valid": spf is not None, "found": spf, "all_records": records}


def check_dkim(domain: str, selector: str, expected_public_b64: Optional[str] = None) -> dict:
    name = f"{selector}._domainkey.{domain}"
    records = _resolve_txt(name)
    dkim = next((r for r in records if "v=DKIM1" in r), None)
    matches = None
    if dkim and expected_public_b64:
        matches = expected_public_b64 in dkim.replace(" ", "")
    return {"valid": dkim is not None, "matches_expected": matches, "found": dkim, "all_records": records}


def check_dmarc(domain: str) -> dict:
    records = _resolve_txt(f"_dmarc.{domain}")
    dmarc = next((r for r in records if r.lower().startswith("v=dmarc1")), None)
    return {"valid": dmarc is not None, "found": dmarc, "all_records": records}


def check_mx(domain: str, expected_host: Optional[str] = None) -> dict:
    records = _resolve_mx(domain)
    matches = None
    if expected_host and records:
        matches = any(expected_host.rstrip(".") in r for r in records)
    return {"valid": len(records) > 0, "matches_expected": matches, "found": records}


def check_dnsbl(ip: str) -> dict:
    bls = ["zen.spamhaus.org", "dnsbl.sorbs.net", "b.barracudacentral.org", "bl.spamcop.net"]
    results = {}
    listed = False
    parts = ip.split('.')
    if len(parts) == 4:
        rev_ip = f"{parts[3]}.{parts[2]}.{parts[1]}.{parts[0]}"
        for bl in bls:
            try:
                answers = dns.resolver.resolve(f"{rev_ip}.{bl}", "A", lifetime=2.0)
                if answers:
                    results[bl] = True
                    listed = True
            except Exception:
                results[bl] = False
    return {"listed": listed, "details": results}


def check_ptr(ip: str) -> dict:
    try:
        import dns.reversename
        rev_name = dns.reversename.from_address(ip)
        answers = dns.resolver.resolve(rev_name, "PTR", lifetime=2.0)
        return {"valid": True, "found": [str(a) for a in answers]}
    except Exception:
        return {"valid": False, "found": []}


def run_full_check(domain: dict) -> dict:
    """Run all checks including SPF, DKIM, DMARC, MX, PTR, and DNSBL."""
    name = domain["name"]
    selector = domain.get("dkim_selector", "mail")
    dkim_pub = domain.get("dkim_public_key")
    mail_host = domain.get("mail_host", "mail")
    expected_mx = f"{mail_host}.{name}"
    
    spf_c = check_spf(name)
    dkim_c = check_dkim(name, selector, dkim_pub)
    dmarc_c = check_dmarc(name)
    mx_c = check_mx(name, expected_mx)

    ip = None
    dnsbl_c = {"listed": False, "details": {}}
    ptr_c = {"valid": False, "found": []}

    if mx_c["found"]:
        try:
            # Extract first MX hostname
            mx_hostname = mx_c["found"][0].split()[-1]
            a_answers = dns.resolver.resolve(mx_hostname, "A", lifetime=2.0)
            ip = str(a_answers[0])
            dnsbl_c = check_dnsbl(ip)
            ptr_c = check_ptr(ip)
        except Exception:
            pass

    recommendations = []
    
    # DMARC Analysis
    dmarc_rec = dmarc_c.get("found")
    if not dmarc_rec:
        recommendations.append({"type": "critical", "msg": "Missing DMARC policy. This makes you vulnerable to domain spoofing."})
    else:
        if "p=none" in dmarc_rec.lower():
            recommendations.append({"type": "warning", "msg": "Weak DMARC policy (p=none). Upgrade to quarantine or reject to protect your domain reputation."})
        if "rua=" not in dmarc_rec.lower():
            recommendations.append({"type": "info", "msg": "DMARC missing RUA tag. You are not receiving aggregate spam reports from Gmail/Outlook."})

    # SPF Analysis
    if not spf_c.get("valid"):
        recommendations.append({"type": "critical", "msg": "Missing SPF record. Your emails will likely go to spam."})
    elif "~all" in spf_c.get("found", "").lower():
        recommendations.append({"type": "info", "msg": "SPF uses SoftFail (~all). Consider StrictFail (-all) when ready."})

    # DKIM Analysis
    if not dkim_c.get("valid"):
        recommendations.append({"type": "critical", "msg": "Missing DKIM signature. Essential for passing modern spam filters."})
    elif not dkim_c.get("matches_expected"):
        recommendations.append({"type": "critical", "msg": "DKIM misalignment. The public key does not match Relayd's private key."})

    # PTR Analysis
    if ip and not ptr_c.get("valid"):
        recommendations.append({"type": "critical", "msg": f"Missing Reverse DNS (PTR) for IP {ip}. Major providers like Gmail will hard bounce your mail."})

    # Blacklist Analysis
    if dnsbl_c.get("listed"):
        bl_names = [k for k, v in dnsbl_c.get("details", {}).items() if v]
        recommendations.append({"type": "critical", "msg": f"Your MX IP ({ip}) is listed on blacklists: {', '.join(bl_names)}"})

    return {
        "spf": spf_c,
        "dkim": dkim_c,
        "dmarc": dmarc_c,
        "mx": mx_c,
        "dnsbl": dnsbl_c,
        "ptr": ptr_c,
        "ip": ip,
        "recommendations": recommendations
    }


def compute_score(checks: dict) -> int:
    score = 0
    if checks.get("spf", {}).get("valid"):
        score += 25
    if checks.get("dkim", {}).get("valid"):
        score += 25
    if checks.get("dmarc", {}).get("valid"):
        score += 25
    if checks.get("mx", {}).get("valid"):
        score += 25
    return score
