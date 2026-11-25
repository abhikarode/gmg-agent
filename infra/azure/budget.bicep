targetScope = 'resourceGroup'

@description('First day of the current UTC month, formatted as YYYY-MM-01.')
param startDate string
@description('Receives cost alerts for the pilot resource group.')
@secure()
param notificationEmail string
@minValue(1)
@maxValue(10)
param monthlyUsd int = 10

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'gmg-agent-pilot'
  properties: {
    amount: monthlyUsd
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
    }
    notifications: {
      fifty: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: [notificationEmail]
      }
      eighty: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [notificationEmail]
      }
      oneHundred: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [notificationEmail]
      }
    }
  }
}
