import asyncio
import libsql_client

async def main():
    client = libsql_client.create_client("file::memory:")
    await client.execute("CREATE TABLE test(id INT)")
    res = await client.execute("INSERT INTO test VALUES (1)")
    print(res.rows_affected)
    
asyncio.run(main())
