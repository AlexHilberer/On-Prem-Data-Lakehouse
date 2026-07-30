module.exports = {
  checkSqlAuth: async (request, user) => {
    if (user === process.env.CUBEJS_SQL_USER) {
      return { password: process.env.CUBEJS_SQL_PASSWORD, securityContext: { role: 'superset' } };
    }
    throw new Error('Invalid SQL API user');
  }
};

