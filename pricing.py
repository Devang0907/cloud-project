"""Optional server-side refresh of USD public list prices."""
import json
import math
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def google_rate(key, sku, units):
    request = Request(
        f"https://cloudbilling.googleapis.com/v1beta/skus/{sku}/price?currencyCode=USD",
        headers={"X-Goog-Api-Key": key},
    )
    with urlopen(request, timeout=12) as response:
        rate = json.load(response)["rate"]
    tiers = rate["tiers"]
    paid_tiers = [tier for tier in tiers
                  if float(tier["listPrice"].get("units", 0))
                  + tier["listPrice"].get("nanos", 0) / 1e9 > 0]
    if len(paid_tiers) != 1:
        raise ValueError("Unexpected Google pricing tiers")
    tier = paid_tiers[0]
    price = tier["listPrice"]
    unit = rate["unitInfo"]
    if price["currencyCode"] != "USD":
        raise ValueError("Unexpected Google pricing tier")
    amount = float(price.get("units", 0)) + price.get("nanos", 0) / 1e9
    return amount * units[unit["unit"]] / float(unit["unitQuantity"]["value"])


def aws_prices(client, service, attributes, unit):
    filters = [{"Type": "TERM_MATCH", "Field": k, "Value": v}
               for k, v in attributes.items()]
    pages = client.get_paginator("get_products").paginate(ServiceCode=service, Filters=filters)
    rates = {}
    for page in pages:
        for product in page["PriceList"]:
            for term in json.loads(product)["terms"]["OnDemand"].values():
                for dimension in term["priceDimensions"].values():
                    if dimension["unit"] != unit:
                        continue
                    start = float(dimension["beginRange"])
                    price = float(dimension["pricePerUnit"]["USD"])
                    if start in rates and rates[start] != price:
                        raise ValueError("Ambiguous AWS pricing")
                    rates[start] = price
    return rates


def refresh_prices():
    key = os.environ.get("GOOGLE_CLOUD_API_KEY")
    if not key:
        raise RuntimeError("Set GOOGLE_CLOUD_API_KEY on the server and enable the Cloud Billing API.")
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        raise RuntimeError("Install boto3 in the server Python environment to refresh AWS prices.") from None
    try:
        client = boto3.client("pricing", region_name="us-east-1",
                              config=Config(connect_timeout=5, read_timeout=12, retries={"max_attempts": 1}))
        ec2 = aws_prices(client, "AmazonEC2", {
            "regionCode": "us-east-1", "instanceType": "m7i.2xlarge", "operatingSystem": "Linux",
            "tenancy": "Shared", "preInstalledSw": "NA", "capacitystatus": "Used", "operation": "RunInstances",
        }, "Hrs")
        s3 = aws_prices(client, "AmazonS3", {
            "regionCode": "us-east-1", "usagetype": "TimedStorage-ByteHrs", "volumeType": "Standard",
        }, "GB-Mo")
        if set(ec2) != {0} or set(s3) != {0, 51200, 512000}:
            raise ValueError("Unexpected AWS tier structure")
        core = google_rate(key, "BB77-5FDA-69D9", {"h": 1})
        ram = google_rate(key, "5B01-D157-A097", {"GiBy.h": 1})
        storage = google_rate(key, "E5F0-6A5D-7BAD", {"GiBy.mo": 1, "GiBy.h": 730})
        rates = dict(aws_vm_hourly=ec2[0], aws_s3_first_50_rate=s3[0],
                     aws_s3_next_450_rate=s3[51200], aws_s3_over_500_rate=s3[512000],
                     gcp_vm_hourly=round(8 * core + 32 * ram, 12), gcp_storage_gib_month=storage)
        if not all(math.isfinite(value) and value > 0 for value in rates.values()):
            raise ValueError("Invalid catalog price")
    except (BotoCoreError, ClientError):
        raise RuntimeError("AWS pricing lookup failed. Check connectivity and credentials with pricing:GetProducts access.") from None
    except HTTPError as error:
        raise RuntimeError(f"Google pricing lookup returned HTTP {error.code}. Check API access and quota.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not reach the Google pricing service. Try again later.") from None
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        raise RuntimeError("Catalog prices or units did not match this scenario. No rates were applied.") from None
    return {"rates": rates, "fetched_at": datetime.now(timezone.utc).isoformat()}
