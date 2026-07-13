# Kubernetes Runbook

## View logs
```bash
kubectl logs -n schemaintern deployment/backend --tail=100
kubectl logs -n schemaintern deployment/frontend --tail=100
```

## Restart a service
```bash
kubectl rollout restart deployment/backend -n schemaintern
```

## Scale a service
```bash
kubectl scale deployment/backend --replicas=5 -n schemaintern
```

## Check pod health
```bash
kubectl get pods -n schemaintern -o wide
kubectl describe pod -n schemaintern <pod-name>
```

## Port forward for debugging
```bash
kubectl port-forward -n schemaintern service/backend 8100:8100
```

## Update image
```bash
kubectl set image deployment/backend backend=ghcr.io/org/upl/backend:latest -n schemaintern
kubectl rollout status deployment/backend -n schemaintern
```

## View resource usage
```bash
kubectl top pods -n schemaintern
kubectl top nodes
```
