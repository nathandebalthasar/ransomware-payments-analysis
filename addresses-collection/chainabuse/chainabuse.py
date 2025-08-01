import asyncio
import json
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

CHAINABUSE_API_URL = "https://www.chainabuse.com/api/graphql-proxy"

async def main():
    transport = AIOHTTPTransport(url=CHAINABUSE_API_URL)
    client = Client(transport=transport, fetch_schema_from_transport=False)

    # Query retrieved from the Chainabuse web interface
    query = gql("""
        query GetReports($input: ReportsInput, $after: String, $before: String, $last: Float, $first: Float) {
            reports(input: $input, after: $after, before: $before, last: $last, first: $first) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        createdAt
                        reportedBy {
                            username
                            trusted
                        }
                        addresses {
                            address
                            chain
                        }
                        scamCategory
                        checked
                        description
                        accusedScammers {
                            info {
                                contact
                            }
                        }
                        evidences {
                            description
                            photo {
                                url
                                description
                            }
                        }
                    }
                }
            }
        }
    """)

    # Filter for ransomware reports with BTC addresses
    variables = {
        "input": {
            "chains": ["BTC"],
            "scamCategories": ["RANSOMWARE"],
            "orderBy": {
                "field": "UPVOTES_COUNT",
                "direction": "DESC"
            }
        },
        "first": 15,
    }

    output_file = "info.txt"

    # Clear the file before writing
    with open(output_file, "w") as f:
        f.write("")

    async with client as session:
        page = 0
        total_kept = 0

        while True:
            print(f"Fetching page {page + 1}...")
            result = await session.execute(query, variable_values=variables)

            edges = result["reports"]["edges"]
            page_info = result["reports"]["pageInfo"]

            with open(output_file, "a") as f:
                for edge in edges:
                    report = edge["node"]
                    author = report.get("reportedBy", {})

                    if author is None:
                        print("Report has no author. Skipping...")
                        continue
                    trusted = author.get("trusted", None)
                    if trusted == True: # Only keep trusted reports
                        total_kept += 1
                        f.write(json.dumps(edge, indent=2) + "\n")
                    elif trusted is None:
                        print(f"Report by {author.get('username', 'Unknown')} is not marked as trusted. Skipping...")

            if page_info["hasNextPage"]:
                if page_info["endCursor"] is None:
                    print("No more pages to fetch.")
                    break

                variables["after"] = page_info["endCursor"]
                page += 1
            else:
                break

    print(f"{total_kept} reports saved to {output_file}.")

asyncio.run(main())
