# Runbook

## Common Issues

- **Ingest API not reachable**
  - Ensure `docker-compose up` is running
  - Check port 8000

- **Dashboard empty**
  - Ensure synthetic generator is running
  - Confirm API URL in generator

- **SQLite lock errors**
  - Stop generator and restart
  - Ensure only one writer at a time

## Useful Commands

```bash
# Check tables
sqlite3 /data/smart_campus.db '.tables'

# Tail alerts
sqlite3 /data/smart_campus.db 'select * from alerts order by id desc limit 5;'
```
