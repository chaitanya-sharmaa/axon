import asyncio
import libsql_client

async def main():
    client = libsql_client.create_client("file:/tmp/test_vec.db")
    await client.execute("CREATE TABLE vecs (id INT, v F32_BLOB(3))")
    await client.execute("INSERT INTO vecs VALUES (1, vector('[1,2,3]'))")
    res = await client.execute("SELECT id, vector_distance_cos(v, vector('[1,2,4]')) as dist FROM vecs")
    print(res.rows[0])

asyncio.run(main())
