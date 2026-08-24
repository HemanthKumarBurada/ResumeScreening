import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Directory where your evaluation CSVs are stored
DATA_DIR = "final_results"
OUTPUT_DIR = "images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Apply a clean academic theme
sns.set_theme(style="whitegrid")

def generate_charts():
    # -------------------------------------------------------------
    # Chart 1: Predicted Score vs. Gold Standard Score (Scatter Plot)
    # -------------------------------------------------------------
    gold_file = os.path.join(DATA_DIR, "gold_pair_results.csv")
    if os.path.exists(gold_file):
        gold_df = pd.read_csv(gold_file)
        
        plt.figure(figsize=(7, 6))
        sns.scatterplot(
            data=gold_df, x='gold_score', y='predicted_score', 
            alpha=0.7, color='#2563eb', edgecolor='k'
        )
        # Ideal fit line (y = x)
        plt.plot([0, 100], [0, 100], color='red', linestyle='--', linewidth=1.5, label='Ideal Fit (y=x)')
        
        plt.title('Predicted Score vs. Gold Standard Score', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Gold Standard Score', fontsize=12, fontweight='bold')
        plt.ylabel('Predicted Hybrid Score ($S_1$)', fontsize=12, fontweight='bold')
        plt.legend(frameon=True)
        sns.despine(top=True, right=True)
        
        out_path1 = os.path.join(OUTPUT_DIR, 'fig1_score_correlation.png')
        plt.tight_layout()
        plt.savefig(out_path1, dpi=300)
        plt.close()
        print(f"Saved: {out_path1}")

    # -------------------------------------------------------------
    # Chart 2: Skill Cascade Match Recall by Tier (Bar Chart)
    # -------------------------------------------------------------
    cascade_file = os.path.join(DATA_DIR, "skill_cascade_results.csv")
    if os.path.exists(cascade_file):
        cascade_df = pd.read_csv(cascade_file)
        
        # Calculate percentage match per tier
        tier_accuracy = cascade_df.groupby('true_tier')['match'].mean().reset_index()
        tier_accuracy['match_pct'] = tier_accuracy['match'] * 100

        plt.figure(figsize=(7, 5))
        bars = plt.bar(
            tier_accuracy['true_tier'], tier_accuracy['match_pct'], 
            color=['#3b82f6', '#10b981', '#f59e0b'], width=0.5, edgecolor='black', linewidth=1
        )
        
        plt.title('Skill Cascade Match Recall by Tier', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Skill Mention Tier', fontsize=12, fontweight='bold')
        plt.ylabel('Recall (%)', fontsize=12, fontweight='bold')
        plt.ylim(0, 115)

        for bar in bars:
            y = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, y + 2, f'{y:.2f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

        sns.despine(top=True, right=True)
        out_path2 = os.path.join(OUTPUT_DIR, 'fig2_skill_cascade_recall.png')
        plt.tight_layout()
        plt.savefig(out_path2, dpi=300)
        plt.close()
        print(f"Saved: {out_path2}")

    # -------------------------------------------------------------
    # Chart 3: Genuine vs. Keyword-Stuffed Resumes (KDE Distribution)
    # -------------------------------------------------------------
    fraud_file = os.path.join(DATA_DIR, "fraud_detection_results.csv")
    if os.path.exists(fraud_file):
        fraud_df = pd.read_csv(fraud_file)
        
        plt.figure(figsize=(8, 5))
        sns.kdeplot(fraud_df['genuine_score'], label='Genuine Resumes', fill=True, color='#3b82f6', alpha=0.4)
        sns.kdeplot(fraud_df['stuffed_score'], label='Keyword-Stuffed Resumes', fill=True, color='#ef4444', alpha=0.4)
        
        plt.title('Screening Score Distribution: Genuine vs. Keyword-Stuffed Resumes', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Screening Score ($S_1$)', fontsize=12, fontweight='bold')
        plt.ylabel('Density', fontsize=12, fontweight='bold')
        plt.legend(frameon=True)
        
        sns.despine(top=True, right=True)
        out_path3 = os.path.join(OUTPUT_DIR, 'fig3_fraud_distribution.png')
        plt.tight_layout()
        plt.savefig(out_path3, dpi=300)
        plt.close()
        print(f"Saved: {out_path3}")

if __name__ == "__main__":
    generate_charts()