#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_CONFIG="$BASE_DIR/config/infra_config.yaml"

read -r -p "Do you want to use SSH tunnel? [y/N] " use_ssh_input
use_ssh_input="${use_ssh_input:-N}"

get_yaml_value() {
  local key="$1"
  local file="$2"
  local value
  value=$(grep -E "^[[:space:]]*${key}:[[:space:]]*" "$file" | head -n1 | sed -E "s/^[^:]+:[[:space:]]*//" | sed -E "s/#.*$//" | sed -E "s/^\"(.*)\"$/\1/" | sed -E "s/^'(.*)'$/\1/" | xargs || true)
  echo "$value"
}

expand_tilde() {
  local path="$1"
  if [[ "$path" == "~" ]]; then
    echo "$HOME"
  elif [[ "$path" == "~/"* ]]; then
    echo "$HOME/${path#~/}"
  else
    echo "$path"
  fi
}

want_ssh=false
case "$use_ssh_input" in
  y|Y|yes|YES) want_ssh=true ;;
  *) want_ssh=false ;;
esac

user_args=("$@")
if [[ ${#user_args[@]} -eq 0 ]]; then
  user_args=("up")
elif [[ "${user_args[0]}" == -* ]]; then
  # If first arg is a flag, prepend "up"
  user_args=("up" "${user_args[@]}")
fi

if $want_ssh; then
  if [[ ! -f "$INFRA_CONFIG" ]]; then
    echo "Missing infra_config.yaml, cannot check remote DB."
  else
    ssh_host=$(get_yaml_value "ssh_host" "$INFRA_CONFIG")
    ssh_port=$(get_yaml_value "ssh_port" "$INFRA_CONFIG")
    ssh_username=$(get_yaml_value "ssh_username" "$INFRA_CONFIG")
    ssh_pkey_path=$(get_yaml_value "ssh_pkey_path" "$INFRA_CONFIG")
    db_host=$(get_yaml_value "db_host" "$INFRA_CONFIG")
    db_port=$(get_yaml_value "db_port" "$INFRA_CONFIG")

    ssh_port="${ssh_port:-22}"
    ssh_pkey_path=$(expand_tilde "$ssh_pkey_path")

    if [[ -n "$ssh_host" && -n "$ssh_username" && -n "$ssh_pkey_path" && -n "$db_host" && -n "$db_port" ]]; then
      echo "Checking remote DB availability over SSH..."
      if ssh -o BatchMode=yes -o ConnectTimeout=5 -p "$ssh_port" -i "$ssh_pkey_path" "$ssh_username@$ssh_host" \
        "bash -c 'exec 3<>/dev/tcp/$db_host/$db_port'" >/dev/null 2>&1; then
        echo "Remote DB is available. PG will not start."
        if [[ "${user_args[0]}" == "up" ]]; then
          cmd=(docker compose up --no-deps)
          if [[ ${#user_args[@]} -gt 1 ]]; then
            cmd+=("${user_args[@]:1}")
          fi
          cmd+=(data_collector analysis_service)
          exec "${cmd[@]}"
        else
          exec docker compose "${user_args[@]}"
        fi
      else
        echo "Remote DB is not available. Local PG will start."
      fi
    else
      echo "Incomplete SSH/DB configuration in infra_config.yaml. Local PG will start."
    fi
  fi
fi

exec docker compose "${user_args[@]}"
