# Basecamp (37signals) cloud repatriation PoC

An IT457 Theme 3 MVP: a Python cost calculator with a local dashboard, an architecture comparison, and a break-even chart. This is a **hypothetical 500 TB / 50 VM workload**, chosen for the class exercise. It is not 37signals' actual infrastructure or invoice.

## Run

Requires Python 3.10 or newer. The baseline runs with the Python standard library.

```powershell
# Run from the project directory
python app.py --serve
```

Open <http://127.0.0.1:8000>. Change assumptions in the sidebar. The graph and itemized cost tables recalculate automatically. To export the entire calculation as JSON:

```powershell
python app.py --json > baseline.json
python app.py --json --inputs example_inputs.json > revised.json
```

The included `example_inputs.json` contains only the fields that differ from the baseline:

```json
{"storage_tb": 600, "servers": 65, "staff_fte": 1.0}
```

Run the checks with `python -m unittest discover -s tests -v` from this folder.

## Architecture being priced

| Component | AWS | Google Cloud | Owned hardware / colocation |
| --- | --- | --- | --- |
| Application compute | 50 × Linux EC2 m7i.2xlarge, 8 vCPU / 32 GiB, us-east-1, 730 h/month | 50 × Linux Compute Engine n2-standard-8, 8 vCPU / 32 GiB, us-central1, 730 h/month | 50 Dell PowerEdge R570-class servers across two facilities; quoted model has 64 GB, so this is a conservative hardware proxy rather than a benchmark-equivalent SKU |
| Object storage | 500 TB logical × 2 S3 Standard region copies | 500 TB logical × 2 Cloud Storage Standard regional copies | 500 TB logical × 2 physical copies, 80% disk fill; 1,250 TB raw, rounded up to 40 × 32 TB drives |
| Facilities | Provider-operated | Provider-operated | Four racks split across two facilities; modeled IT electricity, cooling overhead, and incremental staff |
| Other services | Enter as monthly allowance | Enter as monthly allowance | Network hardware, migration, maintenance, rack space, and hardware refresh |

The two cloud copies follow [37signals' published dual-region storage strategy](https://dev.37signals.com/our-cloud-spend-in-2022/). The modeled 50 VMs are total application capacity in a primary US region; cross-region compute failover is outside this simplified comparison.

## Price inputs and evidence

Prices in USD, checked **28 October 2026**. The MVP reconstructs **list-rate arithmetic**. Shareable estimates were configured in the [AWS Pricing Calculator](https://calculator.aws/#/estimate?id=fd7136cb7c6888e8742a1ea9dfd0009810486920) and [Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator/estimate-preview/CiQ3NGU1OTRiNi0xNDhkLTQ5NDEtYjY1Mi01MWRkNmRlMWJkNWMQAQ%3D%3D). These are planning estimates, not vendor-issued quotes. The AWS public link expires one year after creation.

| Input | Baseline | Evidence or status |
| --- | ---: | --- |
| AWS m7i.2xlarge Linux | $0.4032/hour | [AWS technical presentation](https://d1.awsstatic.com/onedam/marketing-channels/website/aws/en_US/events/approved/reinvent-2025/reinvent/2024/slides/dop/DOP323_NET-application-modernization-to-Linux-using-Amazon-Q-Developer.pdf), p. 5; [instance specification](https://aws.amazon.com/ec2/instance-types/m7i/) |
| AWS S3 Standard | $0.023/GiB-month first 50 TiB; $0.022 next 450 TiB; $0.021 above | [AWS tier table](https://aws.amazon.com/blogs/aws/aws-storage-update-s3-glacier-price-reductions/); [AWS binary billing-unit definition](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_metrics_glossary.html); [current S3 pricing page](https://aws.amazon.com/s3/pricing/) |
| GCP n2-standard-8 | $0.388472/hour | [Google Cloud N2 price table, Iowa](https://cloud.google.com/products/compute/pricing/general-purpose) |
| GCP Standard regional storage | $0.020/GiB-month | [Google Cloud Storage rate table](https://cloud.google.com/storage/pricing): $0.000027397/GiB-hour × 730 ≈ $0.020/GiB-month. [Google's billing-unit definition](https://cloud.google.com/storage/pricing) confirms binary GiB. |
| Dell PowerEdge R570 | $16,598.99/server | [Dell 64 GB model price listing](https://www.dell.com/en-us/shop/ipovw/poweredge-r570). Verify final configuration and support quote. |
| Seagate Exos M 32 TB drive | $1,599.99/drive | [B&H listed in-stock price](https://www.bhphotovideo.com/c/product/1944646-REG/seagate_st32000nm004k_32tb_exos_m_7200.html/overview). Bulk pricing may differ. |
| Rack space | $1,400/rack-month | Planning allowance inside the range of [published colocation rack plans](https://www.astuteinternet.com/services/colocation/order). **Not a space-only quote:** plans may include power and network. Replace with a real two-site quote and avoid double counting power. |
| Commercial electricity | $0.1447/kWh | [EIA August 2026 US commercial average, 14.47¢/kWh](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_es1a). Actual colocator metering differs. |
| Staff salary | $99,130/year × 0.5 incremental FTE × 1.3 burden factor | [BLS May 2025 median for network and systems administrators](https://www.bls.gov/ooh/computer-and-information-technology/network-and-computer-systems-administrators.htm). FTE and benefits factor are planning assumptions. |
| Storage enclosure, network gear, migration | $15,000 × 2; $20,000; $25,000 | Planning allowances; request vendor quotes. |
| Power, cooling, maintenance, refresh | 0.35 kW/server, 0.8 kW/enclosure, 1.2 kW network; PUE 1.4; maintenance 3%/year; five-year full hardware refresh | Planning assumptions, editable in dashboard. No salvage value or inflation. |

## Reproduce in official pricing calculators

1. In the [AWS Pricing Calculator](https://calculator.aws/), add **Amazon EC2**: `us-east-1`, Linux, shared tenancy, `m7i.2xlarge`, quantity 50, 730 hours/month, On-Demand. Add **Amazon S3**: S3 Standard, **465,661.29 GiB-month** in `us-east-1`, and the same Standard amount in a second US region. This is 500 decimal TB (500 trillion bytes) converted to billable GiB. For apples-to-apples arithmetic, exclude request and transfer charges, then add them as separately documented scenarios when actual traffic is known.
2. In the [Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator), add **Compute Engine**: `us-central1`, `n2-standard-8`, 50 instances, 730 hours/month, no commitments. Add **Cloud Storage**: **465,661.29 GiB-month** Standard regional in each of two US regions. Use the same storage unit interpretation and note any calculator rounding.
3. The [saved AWS estimate](https://calculator.aws/#/estimate?id=fd7136cb7c6888e8742a1ea9dfd0009810486920) shows **$35,308.30/month**: EC2 $14,716.80 and S3 $10,295.75 in each of `us-east-1` and `us-east-2`. This matches the model to the cent. The [saved GCP estimate](https://cloud.google.com/products/calculator/estimate-preview/CiQ3NGU1OTRiNi0xNDhkLTQ5NDEtYjY1Mi01MWRkNmRlMWJkNWMQAQ%3D%3D) shows **$32,855.47/month**: Compute Engine $14,229.23 and two Cloud Storage entries of $9,313.12 each. The Google calculator adds its default 10 GiB boot disk per VM, or about $50/month. The model's $32,805.68 excludes VM boot disks and uses the unrounded 465,661.287 GiB storage figure; the $49.79 difference is attributable to those choices and calculator rounding. Export or screenshot both estimates for the final class report.

## Equations and current result

All rates are editable in `model.py`, through the dashboard, or via a JSON override. At baseline:

- AWS compute = `50 × 730 × $0.4032 = $14,716.80/month`.
- Billable storage = `500 × 10¹² bytes / 2³⁰ = 465,661.287 GiB` per region. The first AWS tier is 50 TiB = 51,200 GiB.
- AWS storage = `2 × (51,200 × $0.023 + (465,661.287 − 51,200) × $0.022) = $20,591.50/month`.
- GCP compute = `50 × 730 × $0.388472 = $14,179.228/month`.
- GCP storage = `2 × 465,661.287 × $0.020 = $18,626.45/month`.
- Raw physical storage = `500 TB × 2 copies / 0.8 fill = 1,250 TB`; drive count = `ceil(1,250 / 32) = 40`.
- On-premises monthly power = `IT kW × 730 × $0.1447`; cooling overhead = `IT power × (PUE − 1)`; staff = `0.5 × $99,130 × 1.3 / 12`.
- Cumulative cloud = `monthly cloud total × month`.
- Cumulative owned = `upfront capex + monthly operations × month + replacement hardware × floor((month − 1) / 60)` for positive months. The first purchase serves months 1–60; the first refresh is charged at month 61.

| Baseline output | Amount |
| --- | ---: |
| AWS monthly | $35,308.30 |
| GCP monthly | $32,805.68 |
| On-premises upfront, including migration | $968,949.10 |
| On-premises monthly | $16,331.45 |
| Hardware replacement at months 61, 121, … | $943,949.10 each |
| First month owned is cumulatively cheaper | AWS month 52; GCP month 59 |
| Months owned is cumulatively cheaper over the ten-year chart | AWS months 52–60 and 101–120; GCP months 59–60 and 117–120 |
| Ten-year cumulative total | AWS $4,236,995.60; GCP $3,936,681.54; owned $3,872,671.89 |

**Interpretation:** the first break-even is temporary: a full hardware refresh at month 61 makes owned infrastructure more expensive again. Under these inputs it crosses below both clouds a second time before month 120. The graph shows the step and the comparison at the selected horizon. A single crossing is not a guarantee of durable savings.

## Case-study context and limits

37signals reported [2022 AWS spending of $3.20 million](https://dev.37signals.com/our-cloud-spend-in-2022/) and later described a [roughly $700,000 Dell purchase and nearly $2 million reduction in its annual cloud bill](https://world.hey.com/dhh/our-cloud-exit-savings-will-now-top-ten-million-over-five-years-c7d9b5bd). Its [migration of seven apps took about six months](https://world.hey.com/dhh/we-have-left-the-cloud-251760fb). Those are company-reported facts about a different workload with existing racks and staff; they are **not** substituted into this hypothetical model.

Important unpriced items: storage requests, cross-region replication traffic, internet egress, load balancers, managed database/cache/search, VM block disks, software licenses, backup beyond the two copies, financing, tax, downtime, staffing coverage, and hardware performance validation. Enter defensible monthly allowances or extend the model once measured workload data is available. The financial result is sensitive to on-premises server count and price, rack contracts, staff allocation, power draw, and refresh cycle. Run sensitivity cases before recommending a migration.

## Optional official price refresh

Install the AWS SDK with `python -m pip install boto3`. Configure an AWS profile or role with `pricing:GetProducts` permission. Enable the Cloud Billing API in your Google Cloud project and set `GOOGLE_CLOUD_API_KEY` in the environment that starts the Python server.

In Scenario tuner, select **Refresh cloud prices**. The server looks up Linux shared On-Demand m7i.2xlarge compute and S3 Standard in us-east-1, plus Google N2 Americas CPU and RAM and US regional Standard storage. The scenario applies the selected storage rate to each copy. Hourly Google storage prices are converted using 730 hours per billing month. The fetch timestamp appears after both providers respond. Reset baseline restores the rates used for the saved calculator comparison.

[AWS Price List](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html) · [Google Cloud price API](https://docs.cloud.google.com/billing/docs/how-to/get-pricing-information-api)
