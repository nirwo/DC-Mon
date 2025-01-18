# Shutdown Manager

A web application for managing and monitoring the shutdown sequence of multiple applications and their dependencies.

## CSV Import Format

The system supports importing application data via CSV files. Here's the structure of the CSV file:

| Column | Description | Example |
|--------|-------------|---------|
| team_name | Name of the team responsible for the application | Frontend Team |
| app_name | Name of the application | Customer Portal |
| host | Hostname or IP address of the application | web1.internal |
| port | Port number the application runs on | 8080 |
| webui_url | URL of the application's web interface (if any) | http://web1.internal:8080 |
| db_host | Database host:port (if any) | db1.internal:5432 |
| shutdown_order | Order in which the application should be shut down (higher numbers first) | 100 |
| dependencies | Semicolon-separated list of dependencies (host:port) | auth.internal:9000;user.internal:9001 |

### Sample Data

A sample CSV file (`sample_data.csv`) is provided with example data. This includes:

1. Frontend Applications:
   - Customer Portal
   - Admin Dashboard

2. API Services:
   - Authentication Service
   - User Service
   - Order Service

3. Databases:
   - User Database
   - Order Database

4. Monitoring Stack:
   - Prometheus
   - Grafana
   - Time Series DB

### Shutdown Order

The shutdown_order field determines the sequence of shutdown:
- Higher numbers are shut down first
- Applications with the same shutdown_order are processed in parallel
- Dependencies are automatically considered in the shutdown sequence

### Dependencies

Dependencies are specified as host:port pairs, separated by semicolons. For example:
```
auth.internal:9000;user.internal:9001
```
This means the application depends on both the Authentication Service and User Service.
