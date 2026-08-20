cat << 'EOF' > send_metric.sh
#!/bin/sh
IDLE=$(top -bn1 | grep -i "cpu(s)" | awk -F, '{print $4}' | awk '{print $1}')
USED=$(echo "100 - $IDLE" | bc)
aws cloudwatch put-metric-data \
  --namespace "OnPremMonitoring" \
  --metric-name "CPUUtilization" \
  --value "$USED" \
  --unit "Percent" \
  --region us-east-2
echo "Sent CPU Usage: $USED%"
EOF
chmod +x send_metric.sh