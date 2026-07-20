import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import matplotlib.pyplot as plt

# 1. تحميل البيانات
df = pd.read_csv('data.csv')  # غير اسم الملف حسب ملفك

# 2. فصل المتغيرات
X = df.drop('target', axis=1)  # المتغيرات المستقلة
y = df['target']               # المتغير التابع

# 3. تقسيم البيانات
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 4. تدريب النموذج
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# 5. التوقع
y_pred = model.predict(X_test)

# 6. التقييم
print(f"الدقة: {accuracy_score(y_test, y_pred):.2f}")
print("\nتقرير التصنيف:")
print(classification_report(y_test, y_pred))

# 7. رسم أهمية المتغيرات
importances = model.feature_importances_
plt.barh(X.columns, importances)
plt.show()
