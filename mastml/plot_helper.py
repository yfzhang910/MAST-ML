"""
A collection of functions which make plots (png files) using matplotlib.
Most of these plots take in (data, other_data, ..., savepath, stats, title).
Where the data args are numpy arrays, savepath is a string, and stats is an
ordered dictionary which maps names to either values, or mean-stdev pairs.

A plot can also take an "outdir" instead of a savepath. If this is the case,
it must return a list of filenames where it saved the figures.
"""
import math
import pandas as pd
import itertools
import warnings
from collections import Iterable
from os.path import join
from collections import OrderedDict
from sklearn.model_selection import RepeatedKFold
from sklearn.feature_selection import RFECV, RFE

# Ignore the harmless warning about the gelsd driver on mac.
warnings.filterwarnings(action="ignore", module="scipy",
                        message="^internal gelsd")

import numpy as np
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import learning_curve
from sklearn.feature_selection import RFECV # for feature learning curve

import matplotlib
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure, figaspect
from matplotlib.ticker import MaxNLocator # TODO: used?
from matplotlib.animation import FuncAnimation
from matplotlib.font_manager import FontProperties

from .utils import RFECV_train_test

matplotlib.rc('font', size=18, family='sans-serif') # set all font to bigger
matplotlib.rc('figure', autolayout=True) # turn on autolayout

# HEADERENDER don't delete this line, it's used by ipynb maker

from .ipynb_maker import ipynb_maker # TODO: fix cyclic import
from .metrics import nice_names

def make_train_test_plots(run, path, is_classification, label):
    y_train_true, y_train_pred, y_test_true = \
        run['y_train_true'], run['y_train_pred'], run['y_test_true']
    y_test_pred, train_metrics, test_metrics = \
        run['y_test_pred'], run['train_metrics'], run['test_metrics']

    if is_classification:
        title = 'train_confusion_matrix'
        plot_confusion_matrix(y_train_true, y_train_pred,
                              join(path, title+'.png'), train_metrics,
                              title=title)
        title = 'test_confusion_matrix'
        plot_confusion_matrix(y_test_true, y_test_pred,
                              join(path, title+'.png'), test_metrics,
                              title=title)

    else: # is_regression
        plot_predicted_vs_true((y_train_true, y_train_pred, train_metrics),
                          (y_test_true,  y_test_pred,  test_metrics), path, label=label)

        title = 'train_residuals_histogram'
        plot_residuals_histogram(y_train_true, y_train_pred,
                                 join(path, title+'.png'), train_metrics,
                                 title=title, label=label)
        title = 'test_residuals_histogram'
        plot_residuals_histogram(y_test_true,  y_test_pred,
                                 join(path, title+'.png'), test_metrics,
                                 title=title, label=label)

### Core plotting utilities:

@ipynb_maker
def plot_confusion_matrix(y_true, y_pred, savepath, stats, normalize=False,
                          title='Confusion matrix', cmap=plt.cm.Blues):
    """
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    http://scikit-learn.org/stable/auto_examples/model_selection/plot_confusion_matrix.html
    """
    # calculate confusion matrix and lables in correct order
    cm = confusion_matrix(y_true, y_pred)
    #classes = sorted(list(set(y_true).intersection(set(y_pred))))
    classes = sorted(list(set(y_true).union(set(y_pred))))

    fig, ax = make_fig_ax()

    ax.set_title(title)

    # create the colorbar, not really needed but everyones got 'em
    mappable = ax.imshow(cm, interpolation='nearest', cmap=cmap)
    #fig.colorbar(mappable)

    # set x and y ticks to labels
    tick_marks = range(len(classes))
    ax.set_xticks(tick_marks)
    ax.set_xticklabels(classes, rotation='vertical', fontsize=18)

    ax.set_yticks(tick_marks)
    ax.set_yticklabels(classes, rotation='vertical', fontsize=18)

    # draw number in the boxes
    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        ax.text(j, i, format(cm[i, j], fmt),
                horizontalalignment="center",
                color="white" if cm[i, j] > thresh else "black")

    # plots the stats
    plot_stats(fig, stats)

    ax.set_ylabel('True label')
    ax.set_xlabel('Predicted label')
    fig.savefig(savepath, dpi=250, bbox_inches='tight')

@ipynb_maker
def plot_residuals_histogram(y_true, y_pred, savepath,
                             stats, title='residuals histogram', label='residuals'):

    # make fig and ax, use x_align when placing text so things don't overlap
    x_align = 0.64
    fig, ax = make_fig_ax(x_align=x_align)

    #ax.set_title(title)
    # do the actual plotting
    residuals = y_true - y_pred

    #Output residuals data and stats to spreadsheet
    split = savepath.split('/')
    pathlist = split[0:len(split)-1]
    path = ''
    for p in pathlist:
        if p != '':
            path += '/'+str(p)
    savepath_parse = savepath.split('/')[-1].split('.png')[0]
    pd.DataFrame(residuals).describe().to_csv(path+'/'+savepath_parse+'_'+'residual_statistics.csv')
    pd.DataFrame(residuals).to_csv(path+'/'+savepath_parse+'_'+'residuals.csv')

    #Get num_bins using smarter method
    num_bins = get_histogram_bins(y_df=residuals)
    ax.hist(residuals, bins=num_bins, color='b', edgecolor='k')

    # normal text stuff
    ax.set_xlabel('Value of '+label, fontsize=16)
    ax.set_ylabel('Number of occurences', fontsize=16)

    # make y axis ints, because it is discrete
    #ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    plot_stats(fig, stats, x_align=x_align, y_align=0.90)
    plot_stats(fig, pd.DataFrame(residuals).describe().to_dict()[0], x_align=x_align, y_align=0.60)

    fig.savefig(savepath, dpi=250, bbox_inches='tight')

@ipynb_maker
def plot_target_histogram(y_df, savepath, title='target histogram', label='target values'):

    # make fig and ax, use x_align when placing text so things don't overlap
    x_align = 0.70
    fig, ax = make_fig_ax(aspect_ratio=0.5, x_align=x_align)

    #ax.set_title(title)

    #Get num_bins using smarter method
    num_bins = get_histogram_bins(y_df=y_df)

    # do the actual plotting
    ax.hist(y_df, bins=num_bins, color='b', edgecolor='k')#, histtype='stepfilled')

    # normal text stuff
    ax.set_xlabel('Value of '+label, fontsize=16)
    ax.set_ylabel('Number of occurences', fontsize=16)

    # make y axis ints, because it is discrete
    #ax.yaxis.set_major_locator(MaxNLocator(integer=True))


    plot_stats(fig, dict(y_df.describe()), x_align=x_align, y_align=0.90, fontsize=14)
    # Save input data stats to csv
    savepath_parse = savepath.split('target_histogram.png')[0]
    y_df.describe().to_csv(savepath_parse+'/''input_data_statistics.csv')

    fig.savefig(savepath, dpi=250, bbox_inches='tight')

@ipynb_maker
def plot_predicted_vs_true(train_triple, test_triple, outdir, label):
    filenames = list()
    y_train_true, y_train_pred, train_metrics = train_triple
    y_test_true, y_test_pred, test_metrics = test_triple

    # make diagonal line from absolute min to absolute max of any data point
    # using round because Ryan did - but won't that ruin small numbers??? TODO this
    max1 = round(max(y_train_true.max(), y_train_pred.max(),
               y_test_true.max(), y_test_pred.max()))
    min1 = round(min(y_train_true.min(), y_train_pred.min(),
               y_test_true.min(), y_test_pred.min()))

    for y_true, y_pred, stats, title_addon in \
            (train_triple+('train',), test_triple+('test',)):

        # make fig and ax, use x_align when placing text so things don't overlap
        x_align=0.64
        fig, ax = make_fig_ax(x_align=x_align)

        # set tick labels
        # notice that we use the same max and min for all three. Don't
        # calculate those inside the loop, because all the should be on the same scale and axis
        _set_tick_labels(ax, max1, min1)

        # plot diagonal line
        ax.plot([min1, max1], [min1, max1], 'k--', lw=2, zorder=1)

        # do the actual plotting
        ax.scatter(y_true, y_pred, color='blue', edgecolors='black', s=100, zorder=2, alpha=0.7)

        # set axis labels
        ax.set_xlabel('True '+label, fontsize=16)
        ax.set_ylabel('Predicted '+label, fontsize=16)

        plot_stats(fig, stats, x_align=x_align, y_align=0.90)

        filename = 'predicted_vs_true_'+ title_addon + '.png'
        filenames.append(filename)
        fig.savefig(join(outdir, filename), dpi=250, bbox_inches='tight')

    return filenames

def plot_scatter(x, y, savepath, groups=None, xlabel='x', ylabel='y', label='target data'):
    # Set image aspect ratio:
    fig, ax = make_fig_ax()

    # set tick labels
    max_tick_x = max(x)
    min_tick_x = min(x)

    divisor_y = get_divisor(max(y), min(y))
    max_tick_y = round_up(max(y), divisor_y)
    min_tick_y = round_down(min(y), divisor_y)
    _set_tick_labels_different(ax, max_tick_x, min_tick_x, max_tick_y, min_tick_y)

    if groups is None:
        ax.scatter(x, y, c='b', edgecolor='darkblue', zorder=2, s=100, alpha=0.7)
    else:
        for groupcount, group in enumerate(np.unique(groups)):
            colors = ['blue', 'red', 'green', 'purple', 'orange', 'black', 'yellow']
            shapes = []
            mask = groups == group
            ax.scatter(x[mask], y[mask], label=group, color=colors[groupcount], s=100, alpha=0.7)

    ax.set_xlabel(xlabel, fontsize=16)
    ax.set_ylabel('Value of '+label, fontsize=16)
    fig.savefig(savepath, dpi=250, bbox_inches='tight')

@ipynb_maker
def plot_best_worst_split(y_true, best_run, worst_run, savepath,
                          title='Best Worst Overlay', label='target_value'):

    # make fig and ax, use x_align when placing text so things don't overlap
    x_align = 0.64
    fig, ax = make_fig_ax(x_align=x_align)

    maxx = round(max(y_true)) # TODO is round the right thing here?
    minn = round(min(y_true))
    ax.plot([minn, maxx], [minn, maxx], 'k--', lw=2, zorder=1)

    # set tick labels
    _set_tick_labels(ax, maxx, minn)

    # do the actual plotting
    ax.scatter(best_run['y_test_true'],  best_run['y_test_pred'],  c='red',
               alpha=0.7, label='best',  edgecolor='darkred',  zorder=2, s=100)
    ax.scatter(worst_run['y_test_true'], worst_run['y_test_pred'], c='blue',
               alpha=0.7, label='worst', edgecolor='darkblue', zorder=3, s=80)

    # set axis labels
    ax.set_xlabel('True '+label, fontsize=16)
    ax.set_ylabel('Predicted '+label, fontsize=16)

    #font_dict = {'size'   : 10, 'family' : 'sans-serif'}

    # Duplicate the stats dicts with an additional label
    best_stats = OrderedDict([('Best Run', None)])
    best_stats.update(best_run['test_metrics'])
    worst_stats = OrderedDict([('worst Run', None)])
    worst_stats.update(worst_run['test_metrics'])

    plot_stats(fig, best_stats, x_align=x_align, y_align=0.90)
    plot_stats(fig, worst_stats, x_align=x_align, y_align=0.60)

    fig.savefig(savepath, dpi=250, bbox_inches='tight')

@ipynb_maker
def plot_best_worst_per_point(y_true, y_pred_list, savepath, metrics_dict,
                              avg_stats, title='best worst per point', label='target_value'):
    worsts = []
    bests = []
    new_y_true = []
    for yt, y_pred in zip(y_true, y_pred_list):
        if len(y_pred) == 0 or np.nan in y_pred_list or yt == np.nan:
            continue
        worsts.append(max(y_pred, key=lambda yp: abs(yp-yt)))
        bests.append( min(y_pred, key=lambda yp: abs(yp-yt)))
        new_y_true.append(yt)

    worst_stats = OrderedDict([('Worst combined:', None)])
    best_stats = OrderedDict([('Best combined:', None)])
    for name, (_, func) in metrics_dict.items():
        worst_stats[name] = func(new_y_true, worsts)
        best_stats[name] = func(new_y_true, bests)

    # make fig and ax, use x_align when placing text so things don't overlap
    x_align = 15.5/24 #mmm yum
    fig, ax = make_fig_ax(x_align=x_align)

    # gather max and min
    all_vals = [val for val in worsts+bests if val is not None]
    max1 = max(all_vals)
    min1 = min(all_vals)

    # draw dashed horizontal line
    ax.plot([min1, max1], [min1, max1], 'k--', lw=2, zorder=1)

    # set axis labels
    ax.set_xlabel('True '+label, fontsize=16)
    ax.set_ylabel('Predicted '+label, fontsize=16)

    # set tick labels
    maxx = round(max((max(bests), max(worsts), max(new_y_true))))
    minn = round(min((min(bests), min(worsts), min(new_y_true))))
    _set_tick_labels(ax, maxx, minn)

    make_axis_same(ax, max1, min1)

    ax.scatter(new_y_true, bests,  c='red',  alpha=0.7, label='best',
               edgecolor='darkred',  zorder=2, s=100)
    ax.scatter(new_y_true, worsts, c='blue', alpha=0.7, label='worst',
               edgecolor='darkblue', zorder=3, s=80)

    plot_stats(fig, avg_stats, x_align=x_align, y_align=0.51, fontsize=10)
    plot_stats(fig, worst_stats, x_align=x_align, y_align=0.73, fontsize=10)
    plot_stats(fig, best_stats, x_align=x_align, y_align=0.95, fontsize=10)
    fig.savefig(savepath, dpi=250, bbox_inches='tight')

@ipynb_maker
def plot_predicted_vs_true_bars(y_true, y_pred_list, avg_stats,
                                savepath, title='best worst with bars', label='target_value'):
    " EVERYTHING MUST BE ARRAYS DONT GIVE ME DEM DF "
    means = [nice_mean(y_pred) for y_pred in y_pred_list]
    standard_error_means = [nice_std(y_pred)/np.sqrt(len(y_pred))
                            for y_pred in y_pred_list]
    standard_errors = [nice_std(y_pred) for y_pred in y_pred_list]
    
    # make fig and ax, use x_align when placing text so things don't overlap
    x_align = 0.64
    fig, ax = make_fig_ax(x_align=x_align)

    # gather max and min
    max1 = max(np.nanmax(y_true), np.nanmax(means))
    min1 = min(np.nanmin(y_true), np.nanmin(means))

    # draw dashed horizontal line
    ax.plot([min1, max1], [min1, max1], 'k--', lw=2, zorder=1)

    # set axis labels
    ax.set_xlabel('True '+label, fontsize=16)
    ax.set_ylabel('Predicted '+label, fontsize=16)

    # set tick labels
    maxx = round(max((max(means), max(y_true))))
    minn = round(min((min(means), min(y_true))))
    _set_tick_labels(ax, maxx, minn)

    ax.errorbar(y_true, means, yerr=standard_errors, fmt='o', markerfacecolor='blue', markeredgecolor='black', markersize=10,
                alpha=0.7, capsize=3)

    plot_stats(fig, avg_stats, x_align=x_align, y_align=0.90)
    fig.savefig(savepath, dpi=250, bbox_inches='tight')

def plot_1d_heatmap(xs, heats, savepath, xlabel='x', heatlabel='heats'):
    fig, ax = make_fig_ax()
    ax.bar(xs, heats)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(heatlabel)
    fig.savefig(savepath, dpi=250, bbox_inches='tight')


def plot_2d_heatmap(xs, ys, heats, savepath,
                    xlabel='x', ylabel='y', heatlabel='heat'):
    fig, ax = make_fig_ax()
    scat = ax.scatter(xs, ys, c=heats) # marker='o', lw=0, s=20, cmap=cm.plasma
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    cb = fig.colorbar(scat)
    cb.set_label(heatlabel)
    fig.savefig(savepath, dpi=250, bbox_inches='tight')

def plot_3d_heatmap(xs, ys, zs, heats, savepath,
                    xlabel='x', ylabel='y', zlabel='z', heatlabel='heat'):
    # this import has side effects, needed for 3d plots:
    from mpl_toolkits.mplot3d import Axes3D
    # Set image aspect ratio:
    # (eeds to be wide enough or plot will shrink really skinny)
    w, h = figaspect(0.6)
    fig = Figure(figsize=(w,h))
    FigureCanvas(fig) # modifies fig in place
    ax = fig.add_subplot(111, projection='3d')

    scat = ax.scatter(xs, ys, zs, c=heats)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_zlabel(zlabel)
    cb = fig.colorbar(scat)
    cb.set_label(heatlabel)

    fig.savefig(savepath, dpi=250)

    def animate(i):
        ax.view_init(elev=10., azim=i)
        return [fig]
    anim = FuncAnimation(fig, animate, frames=range(0,90,5), blit=True)
    #anim.save(savepath+'.mp4', fps=5, extra_args=['-vcodec', 'libx264'])
    anim.save(savepath+'.gif', fps=5, dpi=80, writer='imagemagick')

def plot_sample_learning_curve(model, X, y, scoring, savepath='data_learning_curve.png'):

    train_sizes = np.linspace(0.1, 1.0, 20)
    train_sizes, train_scores, valid_scores = learning_curve(model, X, y, train_sizes=train_sizes, scoring=scoring,
                                                             cv=RepeatedKFold(n_splits=5, n_repeats=5))
    mean_train_scores = np.mean(train_scores, axis=1)
    mean_test_scores = np.mean(valid_scores, axis=1)
    train_scores_stdev = np.std(train_scores, axis=1)
    test_scores_stdev = np.std(valid_scores, axis=1)

    # Set image aspect ratio (do custom for learning curve):
    w, h = figaspect(0.75)
    fig = Figure(figsize=(w,h))
    FigureCanvas(fig)
    gs = plt.GridSpec(1, 1)
    ax = fig.add_subplot(gs[0:, 0:])

    # set tick labels
    max_x = max(train_sizes)
    min_x = min(train_sizes)
    # TODO there's a better way
    max_y = round(max(max(mean_train_scores),max(mean_train_scores+train_scores_stdev),max(mean_train_scores-train_scores_stdev),
                     max(mean_test_scores),max(mean_test_scores+test_scores_stdev),max(mean_test_scores-test_scores_stdev)))
    min_y = round(min(min(mean_train_scores),min(mean_train_scores+train_scores_stdev),min(mean_train_scores-train_scores_stdev),
                     min(mean_test_scores),min(mean_test_scores+test_scores_stdev),min(mean_test_scores-test_scores_stdev)))
    _set_tick_labels_different_2(ax, max_x, min_x, max_y, min_y)


    # plot and collect handles h1 and h2 for making legend
    h1 = ax.plot(train_sizes, mean_train_scores, '-o', color='blue', markersize=10, alpha=0.7)[0]
    ax.fill_between(train_sizes, mean_train_scores-train_scores_stdev, mean_train_scores+train_scores_stdev,
                     alpha=0.1, color='blue')
    h2 = ax.plot(train_sizes, mean_test_scores, '-o', color='red', markersize=10, alpha=0.7)[0]
    ax.fill_between(train_sizes, mean_test_scores-test_scores_stdev, mean_test_scores+test_scores_stdev,
                     alpha=0.1, color='red')
    ax.legend([h1, h2], ['train score', 'test score'], loc='lower right', fontsize=12)
    ax.set_xlabel('Number of data points', fontsize=16)
    scoring_name = scoring._score_func.__name__
    scoring_name_nice = ''
    for s in scoring_name.split('_'):
        scoring_name_nice += s + ' '
    ax.set_ylabel(scoring_name_nice, fontsize=16)
    fig.savefig(savepath, dpi=250, bbox_inches='tight')

def plot_feature_learning_curve(model, X, y, scoring=None, savepath='feature_learning_curve.png'):
    X = np.array(X)
    y = np.array(y).reshape(-1, 1)

    # Need to revisit how the averaging stats are done over CV steps
    train_means = list()
    train_stds = list()
    test_means = list()
    test_stds = list()
    num_features = X.shape[1]
    feature_list = [f+1 for f in range(num_features)]
    for feature in range(num_features):
        rfe = RFE(estimator=model, n_features_to_select=feature+1, step=1)
        Xnew = rfe.fit_transform(X,y)
        Xnew = pd.DataFrame(Xnew)
        ranking_list = list(rfe.ranking_)
        top_features = list()
        for i, ranking in enumerate(ranking_list):
            if ranking == 1:
                top_features.append(i)
        # Lame transform here but it works
        df_dict = dict()
        for feature in top_features:
            df_dict[feature] = Xnew[feature]
        Xnew = pd.DataFrame(df_dict)
        Xnew = np.array(Xnew)
        # Now do KFoldCV on model containing feature number of features
        rkf = RepeatedKFold(n_splits=5, n_repeats=5)
        cv_number=1
        train_scores = dict()
        test_scores = dict()
        for trains, tests in rkf.split(Xnew, y):
            model = model.fit(Xnew[trains], y[trains])
            train_vals = model.predict(Xnew[trains])
            test_vals = model.predict(Xnew[tests])
            train_scores[cv_number] = scoring._score_func(train_vals, y[trains])
            test_scores[cv_number] = scoring._score_func(test_vals, y[tests])
            cv_number += 1
        train_means.append(np.mean(list(train_scores.values())))
        train_stds.append(np.std(list(train_scores.values())))
        test_means.append(np.mean(list(test_scores.values())))
        test_stds.append(np.std(list(test_scores.values())))    

    #try:
    #    rfe = RFECV(estimator=model, step=1, cv=RepeatedKFold(n_splits=5, n_repeats=5), scoring=scoring)
    #    rfe = rfe.fit(X, y)
    #except AttributeError:
    #    print('Feature learning curve is made using recursive feature elimination, which requires a sklearn model with'
    #          'either a coef_ or feature_importances_ attribute. For regression tasks, use one of: LinearRegression, SVR,'
    #          'Lasso, or RandomForestRegressor')

    # Set image aspect ratio (do custom for learning curve):
    w, h = figaspect(0.75)
    fig = Figure(figsize=(w,h))
    FigureCanvas(fig)
    gs = plt.GridSpec(1, 1)
    ax = fig.add_subplot(gs[0:, 0:])

    max_x = max(feature_list)
    min_x = min(feature_list)
    max_y = round(max(max(train_means),max(np.array(train_means)-np.array(train_stds)),max(np.array(train_means)+np.array(train_stds)),
                     max(test_means),max(np.array(test_means)-np.array(test_stds)),max(np.array(test_means)+np.array(test_stds))))
    min_y = round(min(min(train_means),min(np.array(train_means)-np.array(train_stds)),min(np.array(train_means)+np.array(train_stds)),
                      min(test_means),min(np.array(test_means)-np.array(test_stds)),min(np.array(test_means)+np.array(test_stds))))
    _set_tick_labels_different_2(ax, max_x, min_x, max_y, min_y)
    ax.set_xlabel('Number of features selected', fontsize=16)
    scoring_name = scoring._score_func.__name__
    scoring_name_nice = ''
    for s in scoring_name.split('_'):
        scoring_name_nice += s + ' '
    ax.set_ylabel(scoring_name_nice, fontsize=16)

    """
    features = range(len(rfe.grid_scores_))
    scores = rfe.grid_scores_    
    """

    #h1 = ax.plot(features, scores, '-o', color='blue', markersize=10, alpha=0.7)[0]

    h1 = ax.plot(feature_list, train_means, '-o', color='blue', markersize=10, alpha=0.7)[0]
    ax.fill_between(feature_list, np.array(train_means)-np.array(train_stds), np.array(train_means)+np.array(train_stds),
                    alpha=0.1, color='blue')
    h2 = ax.plot(feature_list, test_means, '-o', color='red', markersize=10, alpha=0.7)[0]
    ax.fill_between(feature_list, np.array(test_means)-np.array(test_stds), np.array(test_means)+np.array(test_stds),
                    alpha=0.1, color='red')
    ax.legend([h1, h2], ['train score', 'test score'], loc='lower right', fontsize=12)

    #ax.legend([h1], ['test score'], loc='upper right', fontsize=12)
    fig.savefig(savepath, dpi=250, bbox_inches='tight')

### Helpers:

def get_histogram_bins(y_df):
    bin_dividers = np.linspace(y_df.shape[0], round(0.05*y_df.shape[0]), y_df.shape[0])
    bin_list = list()
    try:
        for divider in bin_dividers:
            if divider == 0:
                continue
            bins = int((y_df.shape[0])/divider)
            if bins < y_df.shape[0]/2:
                bin_list.append(bins)
    except:
        num_bins = 10
    if len(bin_list) > 0:
        num_bins = max(bin_list)
    else:
        num_bins = 10
    return num_bins

def stat_to_string(name, value):
    " Stringifies the name value pair for display within a plot "
    if name in nice_names:
        name = nice_names[name]
    else:
        name = name.replace('_', ' ')

    # has a name only
    if not value:
        return name
    # has a mean and std
    if isinstance(value, tuple):
        mean, std = value
        return f'{name}:' + '\n\t' + f'{mean:.3f}' + r'$\pm$' + f'{std:.3f}'
    # has a name and value only
    if isinstance(value, int) or (isinstance(value, float) and value%1 == 0):
        return f'{name}: {int(value)}'
    if isinstance(value, float):
        return f'{name}: {value:.3f}'
    return f'{name}: {value}' # probably a string

def plot_stats(fig, stats, x_align=0.65, y_align=0.90, font_dict=dict(), fontsize=14):
    """
    Print stats onto the image
    Goes off screen if they are too long or too many in number
    """

    stat_str = '\n'.join(stat_to_string(name, value)
                           for name,value in stats.items())

    fig.text(x_align, y_align, stat_str,
             verticalalignment='top', wrap=True, fontdict=font_dict, fontproperties=FontProperties(size=fontsize))

def make_fig_ax(aspect_ratio=0.5, x_align=0.65):
    """
    Using Object Oriented interface from
    https://matplotlib.org/gallery/api/agg_oo_sgskip.html
    """
    # Set image aspect ratio:
    w, h = figaspect(aspect_ratio)
    fig = Figure(figsize=(w,h))
    FigureCanvas(fig)

    # Set custom positioning, see this guide for more details:
    # https://python4astronomers.github.io/plotting/advanced.html
    left   = 0.10
    bottom = 0.15
    right  = 0.01
    top    = 0.05
    width = x_align - left - right
    height = 1 - bottom - top
    ax = fig.add_axes((left, bottom, width, height), frameon=True)
    fig.set_tight_layout(False)
    
    return fig, ax

def make_fig_ax_square(aspect='equal', aspect_ratio=1):
    """
    Using Object Oriented interface from
    https://matplotlib.org/gallery/api/agg_oo_sgskip.html
    """
    # Set image aspect ratio:
    w, h = figaspect(aspect_ratio)
    fig = Figure(figsize=(w,h))
    FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect=aspect)

    return fig, ax

def make_axis_same(ax, max1, min1):
    # fix up dem axis
    if max1 - min1 > 5:
        step = (int(max1) - int(min1)) // 3
        ticks = range(int(min1), int(max1)+step, step)
    else:
        ticks = np.linspace(min1, max1, 5)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)

def nice_mean(ls):
    " Returns NaN for empty list "
    if len(ls) > 0:
        return np.mean(ls)
    return np.nan

def nice_std(ls):
    " Returns NaN for empty list "
    if len(ls) > 0:
        return np.std(ls)
    return np.nan

def round_down(num, divisor):
    return num - (num%divisor)

def round_up(num, divisor):
    return float(math.ceil(num / divisor)) * divisor

def get_divisor(high, low):
    delta = high-low
    divisor = 10
    if delta > 1000:
        divisor = 100
    if delta < 1000:
        if delta > 100:
            divisor = 10
        if delta < 100:
            if delta > 10:
                divisor = 1
            if delta < 10:
                if delta > 1:
                    divisor = 0.1
                if delta < 1:
                    if delta > 0.01:
                        divisor = 0.001
                else:
                    divisor = 0.001
    return divisor


# Credit: https://www.linkedin.com/pulse/ask-recursion-during-coding-interviews-identify-good-talent-veteanu/
# not used yet, should be used to refactor some of the min and max bits
def recursive_max(array):
    return max(
        max_number(e) if isinstance(e, Iterable) else e
        for e in array
    )

def recursive_min(array):
    return min(
        max_number(e) if isinstance(e, Iterable) else e
        for e in array
    )

def _set_tick_labels(ax, maxx, minn):
    divisor = get_divisor(maxx, minn)
    max_tick = round_up(maxx, divisor)
    min_tick = round_down(minn, divisor)
    tickvals = np.linspace(min_tick, max_tick, num=5)
    tickvals = [int(val) for val in tickvals]
    ax.set_xticks(ticks=tickvals)
    ax.set_yticks(ticks=tickvals)
    ticklabels = [str(tick) for tick in tickvals]
    ax.set_xticklabels(labels=ticklabels, fontsize=14)
    ax.set_yticklabels(labels=ticklabels, fontsize=14)


def _set_tick_labels_different(ax, max_tick_x, min_tick_x, max_tick_y, min_tick_y):
    " Use this when X and y are over completely diffent ranges. "
    tickvals_x = np.linspace(min_tick_x, max_tick_x, num=5)
    tickvals_x = [round(float(val),1) for val in tickvals_x]

    tickvals_y = np.linspace(min_tick_y, max_tick_y, num=5)
    tickvals_y = [round(float(val),1) for val in tickvals_y]

    ax.set_xticks(ticks=tickvals_x)
    ax.set_yticks(ticks=tickvals_y)

    ticklabels_x = [str(tick) for tick in tickvals_x]
    ticklabels_y = [str(tick) for tick in tickvals_y]

    ax.set_xticklabels(labels=ticklabels_x, fontsize=14)
    ax.set_yticklabels(labels=ticklabels_y, fontsize=14)

# TODO combine with the above. They should be the same thing
# but someone let them diverge because they didn't want to refactor
def _set_tick_labels_different_2(ax, max_x, min_x, max_y, min_y):
    " not suyre how this is different from the above"
    divisor_y = get_divisor(max_y, min_y)
    divisor_x = get_divisor(max_x, min_x)
    max_tick_y = round_up(max_y, divisor_y)
    min_tick_y = round_down(min_y, divisor_y)
    max_tick_x = round_up(max_x, divisor_x)
    min_tick_x = round_down(min_x, divisor_x)
    tickvals_y = np.linspace(min_tick_y, max_tick_y, num=5)
    tickvals_y = [float(val) for val in tickvals_y]
    tickvals_x = np.linspace(min_tick_x, max_tick_x, num=5)
    tickvals_x = [int(val) for val in tickvals_x]
    ax.set_xticks(ticks=tickvals_x)
    ax.set_yticks(ticks=tickvals_y)
    ticklabels_y = [str(tick) for tick in tickvals_y]
    ticklabels_x = [str(tick) for tick in tickvals_x]
    ax.set_xticklabels(labels=ticklabels_x, fontsize=14)
    ax.set_yticklabels(labels=ticklabels_y, fontsize=14)
