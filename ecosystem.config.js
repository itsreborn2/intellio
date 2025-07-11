module.exports = {
  apps: [
    {
      name: 'main',
      script: 'node_modules/.bin/next',
      args: 'start -p 3000',
      cwd: 'frontend/main',
      watch: false,
      autorestart: true,
      instances: 2,
      exec_mode: 'cluster',
      env: {
        NODE_ENV: 'production',
      },
    },
    {
      name: 'doceasy',
      script: 'node_modules/.bin/next',
      args: 'start -p 3010',
      cwd: 'frontend/doceasy',
      watch: false,
      autorestart: true,
      instances: 2,
      exec_mode: 'cluster',
      env: {
        NODE_ENV: 'production',
      },
    },
    {
      name: 'stockeasy',
      script: 'node_modules/.bin/next',
      args: 'start -p 3020',
      cwd: 'frontend/stockeasy',
      watch: false,
      autorestart: true,
      instances: 2,
      exec_mode: 'cluster',
      env: {
        NODE_ENV: 'production',
      },
    },
  ],
};
