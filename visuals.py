import plotly.graph_objects as go

def draw_radar_chart(stats, labels):
    top5_labels = labels[:5]
    top5_values = [stats[label] for label in top5_labels]
    # 오각형 닫기
    r_values = top5_values + [top5_values[0]]
    theta_labels = top5_labels + [top5_labels[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=r_values, theta=theta_labels,
        fill='toself', fillcolor='rgba(255, 215, 0, 0.4)',
        line=dict(color='#FFD700', width=4)
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, max(top5_values)*1.2], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=14, color='white', weight='bold'), rotation=90, direction="clockwise")
        ),
        showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=400, margin=dict(l=50, r=50, t=30, b=30)
    )
    return fig