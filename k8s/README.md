# Kubernetes Deployment Guide for Process MCP Server

This guide walks you through deploying the Oil Stabilization Process MCP Server to a Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (v1.24+)
- `kubectl` configured to access your cluster
- Docker or compatible container registry
- Container image pushed to registry (e.g., `omdv/process-mcp-server:latest`)

## Quick Start

### 1. Build and Push Docker Image

```bash
# Build the Docker image
docker build -t omdv/process-mcp-server:latest .

# Push to your container registry
docker push omdv/process-mcp-server:latest
```

### 2. Deploy Using Kustomize (Recommended)

```bash
# Create namespace
kubectl create namespace mcp

# Deploy all resources using kustomize
kubectl apply -k k8s/

# Or deploy to specific namespace
kubectl apply -k k8s/ --namespace=mcp
```

### 3. Deploy Using kubectl (Alternative)

```bash
# Create namespace (optional)
kubectl create namespace mcp

# Apply configurations
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

### 4. Verify Deployment

```bash
# Check pod status
kubectl get pods -l app=process-mcp-server -n mcp

# View logs
kubectl logs -l app=process-mcp-server -n mcp --tail=100 -f

# Check service
kubectl get svc process-mcp-server -n mcp
```

## Configuration

### Environment Variables

The server uses minimal configuration. All settings are in `configmap.yaml`:

- `LOG_LEVEL`: Logging level (INFO, DEBUG, WARNING, ERROR) - default: INFO
- `PYTHONUNBUFFERED`: Python unbuffered output - default: 1
- `npm_config_cache`: NPM cache directory for supergateway - default: /tmp/.npm

### Resource Limits

Default resource configuration (commented out in deployment.yaml):

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

**Recommendation for Production**: Uncomment and adjust based on your simulation workload. NeqSim simulations can be CPU-intensive.

## Architecture

The deployment uses:

1. **MCP Server**: Python stdio-based MCP server (`mcp_server.py`)
2. **Supergateway**: Wraps the stdio server with HTTP/GraphQL interface
3. **Transport**: Stateless streamable HTTP (no session state on server)

```
Client (n8n/Claude) → Ingress → Service → Pod (supergateway → mcp_server.py → NeqSim)
```

## Scaling

### Horizontal Scaling

```bash
# Scale to 3 replicas
kubectl scale deployment process-mcp-server --replicas=3 -n mcp

# Or use HPA (Horizontal Pod Autoscaler)
kubectl autoscale deployment process-mcp-server \
  --cpu-percent=80 \
  --min=2 \
  --max=10 \
  -n mcp
```

**Note**: The server is stateless, so horizontal scaling works perfectly for handling concurrent simulation requests.

### Vertical Scaling

Edit resource requests/limits in `k8s/deployment.yaml` based on simulation complexity.

## Networking

### Internal Access (ClusterIP)

Default service type is `ClusterIP`, accessible only within the cluster:

```bash
# Access from within cluster
curl http://process-mcp-server.mcp.svc.cluster.local:8000/mcp
```

### External Access via Ingress

The ingress is configured for external access:

- **Host**: `process-mcp-server.kblb.io`
- **Path**: `/mcp`
- **TLS**: Enabled with Let's Encrypt

Update `k8s/ingress.yaml` with your domain:

```yaml
spec:
  tls:
    - hosts:
        - your-domain.com
      secretName: my-certs-process-mcp-server
  rules:
    - host: your-domain.com
```

## Security

The deployment follows security best practices:

1. **Non-root user**: Runs as user 1000
2. **Read-only root filesystem**: Enabled
3. **Dropped capabilities**: All capabilities dropped
4. **No privilege escalation**: Disabled
5. **TLS/SSL**: Enabled via cert-manager and Let's Encrypt

## Monitoring and Logging

### View Logs

```bash
# Stream logs from all pods
kubectl logs -l app=process-mcp-server -n mcp -f --all-containers=true

# Logs from specific pod
kubectl logs <pod-name> -n mcp -f

# Previous pod logs (after crash)
kubectl logs <pod-name> -n mcp --previous
```

### Metrics

The deployment includes Prometheus annotations:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
```

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod for events
kubectl describe pod <pod-name> -n mcp

# Check logs
kubectl logs <pod-name> -n mcp

# Check resource constraints
kubectl top pods -n mcp
```

### Test Connectivity

```bash
# Test from within cluster
kubectl run debug --rm -it --image=curlimages/curl -n mcp -- sh
# Inside pod:
curl http://process-mcp-server:8000/health
```

### Performance Issues

```bash
# Check resource usage
kubectl top pods -l app=process-mcp-server -n mcp

# View detailed metrics
kubectl describe pod <pod-name> -n mcp | grep -A 5 Resources
```

## Updating the Deployment

### Rolling Update

```bash
# Update image
kubectl set image deployment/process-mcp-server \
  process-mcp-server=omdv/process-mcp-server:v2 \
  -n mcp

# Watch rollout
kubectl rollout status deployment/process-mcp-server -n mcp

# Rollback if needed
kubectl rollout undo deployment/process-mcp-server -n mcp
```

### Update Configuration

```bash
# Edit ConfigMap
kubectl edit configmap process-mcp-config -n mcp

# Restart pods to pick up changes
kubectl rollout restart deployment/process-mcp-server -n mcp
```

## Testing the MCP Server

Once deployed, you can test the server:

```bash
# Get the external URL (if ingress is configured)
kubectl get ingress process-mcp-server -n mcp

# Test simulation endpoint
curl -X POST https://process-mcp-server.kblb.io/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { callTool(name: \"simulate_oil_stabilization\", arguments: {}) { content { text } } }"
  }'
```

## Production Checklist

- [ ] Container image built and pushed to registry
- [ ] Image tag updated in `kustomization.yaml` or `deployment.yaml`
- [ ] Ingress domain configured for your environment
- [ ] Resource limits configured appropriately for simulation workload
- [ ] Health checks verified
- [ ] Monitoring and alerting set up
- [ ] Logging aggregation configured
- [ ] TLS/SSL certificates configured
- [ ] Auto-scaling configured (if needed)
- [ ] Backup strategy documented

## Clean Up

To remove all resources:

```bash
# Using kustomize
kubectl delete -k k8s/

# Or using kubectl
kubectl delete deployment,service,configmap,ingress,serviceaccount -l app=process-mcp-server -n mcp

# Delete namespace (if created)
kubectl delete namespace mcp
```

## Support and Documentation

- NeqSim Documentation: https://equinor.github.io/neqsim/
- MCP Protocol: https://modelcontextprotocol.io/
- Kubernetes Documentation: https://kubernetes.io/docs/
- Server Source: `/home/om/Documents/projects/process-mcp-server/mcp_server.py`
