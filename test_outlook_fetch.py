import asyncio
from inbound_gw_agent.connectors.outlook_com import OutlookComClient

async def test():
    client = OutlookComClient()
    emails = await client.get_today_emails()
    print(f"오늘 읽어온 메일 수: {len(emails)}")
    for e in emails:
        print(f"  - {e['receivedDateTime']} | {e['subject'][:60]}")

asyncio.run(test())
